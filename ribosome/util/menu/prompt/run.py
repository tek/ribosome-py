from typing import TypeVar, Callable, Tuple
from queue import Queue

from amino import do, Do, IO, List, Nil, Maybe, Nothing, Just
from amino.logging import module_log
from amino.case import Case
from amino.lenses.lens import lens

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.io.api import N
from ribosome.nvim.io.state import NS
from ribosome.util.menu.prompt.data import (Input, InputState, InputResources, InputChar, PrintableChar, SpecialChar,
                                            PromptInputAction, PromptInput, PromptInterrupt, Prompt, ProcessPrompt,
                                            PromptEcho, PromptAction, PromptStateTrans, PromptQuit, PromptUnit,
                                            PromptQuitWith, PromptUpdate, PromptUpdateChar, PromptConsumerInput,
                                            PromptUpdateConsumer, PromptInit, PromptUpdateInit)
from ribosome.nvim.api.command import nvim_atomic_commands
from ribosome.util.menu.prompt.input import input_loop
from ribosome.util.menu.prompt.interrupt import intercept_interrupt, stop_prompt, stop_prompt_s
from ribosome.compute.prog import Prog

log = module_log()
A = TypeVar('A')
B = TypeVar('B')


class process_char(Case[InputChar, NS[InputState[A, B], None]], alg=InputChar):

    def printable(self, a: PrintableChar) -> NS[InputState[A, B], None]:
        return NS.modify(lambda s: s.append1.actions(PromptUpdateChar(a)))

    def special(self, a: SpecialChar) -> NS[InputState[A, B], None]:
        return NS.modify(lambda s: s.append1.actions(PromptUpdateChar(a)))


def prompt_fragment(text: str, highlight: Maybe[str]) -> List[str]:
    hl = highlight.get_or_strict('None')
    return List(f'echohl {hl}', f'echon "{text}"')


@do(NS[InputState[A, B], None])
def redraw_prompt() -> Do:
    prompt, cursor = yield NS.inspect(lambda s: (s.prompt, s.cursor))
    pre, cursor_char, post = prompt.pre, prompt.post[:1], prompt.post[1:]
    cmds = List((pre, Nothing), (cursor_char, Just('RibosomePromptCaret')), (post, Nothing)).flat_map2(prompt_fragment)
    yield NS.lift(nvim_atomic_commands(cmds.cons('redraw')))


@do(NS[InputState[A, B], None])
def redraw_if_echoing() -> Do:
    state = yield NS.inspect(lambda a: a.state)
    yield redraw_prompt() if isinstance(state, PromptEcho) else NS.unit


class update_prompt_text(Case[InputChar, Prompt], alg=InputChar):

    def __init__(self, prompt: Prompt) -> None:
        self.prompt = prompt

    def printable(self, a: PrintableChar) -> Prompt:
        return self.prompt.copy(cursor=self.prompt.cursor + 1, pre=self.prompt.pre + a.char)

    def special(self, a: SpecialChar) -> Prompt:
        return self.prompt


@do(IO[List[PromptInputAction[A]]])
def dequeue(inputs: Queue) -> Do:
    first = yield IO.delay(inputs.get)
    tail = yield dequeue(inputs) if inputs.qsize() > 0 else IO.pure(Nil)
    return tail.cons(first)


class process_input(Case[PromptInputAction[A], Maybe[PromptUpdate[A]]], alg=PromptInputAction):

    def init(self, a: PromptInit[A]) -> Maybe[PromptUpdate[A]]:
        return Just(PromptUpdateInit())

    def input(self, a: PromptInput[A]) -> Maybe[PromptUpdate[A]]:
        return Just(PromptUpdateChar(a.char))

    def interrupt(self, a: PromptInterrupt[A]) -> Maybe[PromptUpdate[A]]:
        return Nothing

    def consumer(self, a: PromptConsumerInput[A]) -> Maybe[PromptUpdate[A]]:
        return Just(PromptUpdateConsumer(a.data))


class execute_prompt_action(Case[PromptAction, NS[InputResources[A, B], None]], alg=PromptAction):

    def state_trans(self, a: PromptStateTrans) -> NS[InputResources[A, B], None]:
        return NS.modify(lens.state.state.set(a.state))

    def quit(self, a: PromptQuit) -> NS[InputResources[A, B], None]:
        return stop_prompt_s()

    @do(NS[InputResources[A, B], None])
    def quit_with(self, a: PromptQuitWith) -> Do:
        yield NS.modify(lens.state.result.set(Just(a.prog)))
        yield stop_prompt_s()

    def unit(self, a: PromptUnit) -> NS[InputResources[A, B], None]:
        return NS.unit


class process_prompt_update_char(Case[PromptUpdate[B], NS[InputState[A, B], None]], alg=PromptUpdate):

    def init(self, a: PromptUpdateInit[B]) -> NS[InputState[A, B], None]:
        return NS.unit

    def char(self, update: PromptUpdateChar[B]) -> NS[InputState[A, B], None]:
        return NS.modify(lambda s: s.mod.prompt(lambda a: update_prompt_text(a)(update.char)))

    def consumer(self, a: PromptUpdateConsumer[B]) -> NS[InputState[A, B], None]:
        return NS.unit


@do(NS[InputResources[A, B], None])
def process_prompt_update(process: ProcessPrompt, action: PromptUpdate[B]) -> Do:
    yield process_prompt_update_char.match(action).zoom(lens.state)
    yield redraw_if_echoing().zoom(lens.state)
    action = yield process(action).zoom(lens.state)
    yield execute_prompt_action.match(action)


def update_prompt(process: ProcessPrompt) -> Callable[[List[PromptUpdate[B]]], NS[InputResources[A, B], None]]:
    def update_prompt(chars: List[PromptUpdate[B]]) -> NS[InputState[A, B], None]:
        return chars.traverse(lambda char: process_prompt_update(process, char), NS).replace(None)
    return update_prompt


class process_action(Case[PromptUpdate[B], NS[InputState[A, B], None]], alg=PromptUpdate):

    def init(self, a: PromptUpdateInit[B]) -> NS[InputState[A, B], None]:
        return NS.modify(lambda s: s.append1.actions(a))

    def input_char(self, a: PromptUpdateChar[B]) -> NS[InputState[A, B], None]:
        return process_char.match(a.char)

    def custom(self, a: PromptUpdateConsumer[B]) -> NS[InputState[A, B], None]:
        return NS.modify(lambda s: s.append1.actions(a))


def pop_actions(s: InputState[A, B]) -> NvimIO[Tuple[InputState[A, B], List[PromptUpdate[B]]]]:
    return N.pure((s.set.actions(Nil), s.actions))


@do(NS[InputResources[A, B], None])
def prompt_recurse(input: List[PromptUpdate[B]]) -> Do:
    stop = yield NS.inspect(lambda a: a.stop)
    yield input.traverse(process_action.match, NS).zoom(lens.state)
    current = yield NS.apply(pop_actions).zoom(lens.state)
    update = yield NS.inspect(lambda s: s.update)
    yield update(current)
    yield NS.unit if stop.is_set() else prompt_loop()


@do(NS[InputResources[A, B], None])
def prompt_loop() -> Do:
    inputs = yield NS.inspect(lambda s: s.inputs)
    input = yield NS.from_io(dequeue(inputs))
    actions = input.traverse(process_input.match, Maybe)
    yield actions.cata_strict(prompt_recurse, NS.unit)


@do(NS[InputResources[A, B], None])
def start_prompt_loop() -> Do:
    inputs = yield NS.inspect(lambda s: s.inputs)
    yield NS.from_io(IO.delay(inputs.put, PromptInit()))
    yield prompt_loop()


@do(NvimIO[Tuple[Prog[None], A]])
def prompt(process: ProcessPrompt, initial: A) -> Do:
    log.debug(f'running prompt with {initial}')
    res = InputResources.cons(
        InputState.cons(initial),
        update_prompt(process),
    )
    input_thread = yield N.fork(input_loop, res)
    result = yield intercept_interrupt(res.inputs, res.stop, res, start_prompt_loop().run_s(res))
    yield N.from_io(stop_prompt(res.inputs, res.stop))
    yield N.simple(input_thread.join)
    return (result.state.result, result.state.data)


__all__ = ('prompt',)
