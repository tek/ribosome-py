from typing import TypeVar, Callable, Tuple
from queue import Queue

from amino import do, Do, IO, List, Nil, Maybe, Nothing, Just, Map
from amino.logging import module_log
from amino.case import Case
from amino.lenses.lens import lens

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.io.api import N
from ribosome.nvim.io.state import NS
from ribosome.util.menu.prompt.data import (InputState, InputResources, InputChar, PrintableChar, SpecialChar,
                                            PromptInputAction, PromptInput, PromptInterrupt, Prompt, PromptConsumer,
                                            PromptEcho, PromptAction, PromptStateTrans, PromptQuit, PromptUnit,
                                            PromptUpdate, PromptUpdateChar, PromptConsumerInput, PromptUpdateConsumer,
                                            PromptInit, PromptUpdateInit, PromptConsumerUpdate, PromptConsumerInit,
                                            PromptConsumerChanged, PromptConsumerUnhandled, PromptConsumerLocal,
                                            PromptPassthrough)
from ribosome.nvim.api.command import nvim_atomic_commands
from ribosome.util.menu.prompt.input import input_loop
from ribosome.util.menu.prompt.interrupt import intercept_interrupt, stop_prompt, stop_prompt_s

log = module_log()
A = TypeVar('A')
B = TypeVar('B')
C = TypeVar('C')


@do(NS[InputState[A, B], C])
def prompt_state_fork(
        echo: Callable[[], NS[InputState[A, B], C]],
        passthrough: Callable[[], NS[InputState[A, B], C]],
) -> Do:
    state = yield NS.inspect(lambda a: a.state)
    yield (
        echo()
        if isinstance(state, PromptEcho) else
        passthrough()
    )


def prompt_state_fork_strict(echo: C, passthrough: C) -> NS[InputState[A, B], C]:
    return prompt_state_fork(
        lambda: NS.pure(echo),
        lambda: NS.pure(passthrough),
    )


def prompt_if_echoing(thunk: Callable[[], NS[InputState[A, B], C]]) -> NS[InputState[A, B], C]:
    return prompt_state_fork(thunk, lambda: NS.unit)


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


def insert_char(char: str) -> Callable[[Prompt], Prompt]:
    def insert_char(prompt: Prompt) -> Prompt:
        log.debug(f'inserting {char} into prompt')
        return prompt.copy(cursor=prompt.cursor + 1, pre=prompt.pre + char)
    return insert_char


def backspace(prompt: Prompt) -> Prompt:
    log.debug('applying backspace to prompt')
    parts = Just((prompt.pre[-1:], prompt.pre[:-1])) if len(prompt.pre) > 0 else Nothing
    return parts.map2(lambda l, i: prompt.copy(pre=i, cursor=prompt.cursor - 1)).get_or_strict(prompt)


special_prompt_keys = Map({
    '<space>': insert_char(' '),
    '<bs>': backspace,
})


class update_prompt_text(Case[InputChar, Maybe[Prompt]], alg=InputChar):

    def __init__(self, prompt: Prompt) -> None:
        self.prompt = prompt

    def printable(self, a: PrintableChar) -> Prompt:
        return Just(insert_char(a.char)(self.prompt))

    def special(self, a: SpecialChar) -> Prompt:
        return special_prompt_keys.lift(a.char).map(lambda f: f(self.prompt))


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

    def unit(self, a: PromptUnit) -> NS[InputResources[A, B], None]:
        return NS.unit


class process_prompt_update_char(
        Case[PromptUpdate[B], NS[InputState[A, B], PromptConsumerUpdate[B]]],
        alg=PromptUpdate,
):

    def init(self, a: PromptUpdateInit[B]) -> NS[InputState[A, B], PromptConsumerUpdate[B]]:
        return NS.pure(PromptConsumerInit())

    def char(self, update: PromptUpdateChar[B]) -> NS[InputState[A, B], PromptConsumerUpdate[B]]:
        def apply_char(s: InputState[A, B]) -> NvimIO[Tuple[InputState[A, B], PromptConsumerUpdate[B]]]:
            return N.pure(update_prompt_text(s.prompt)(update.char).cata(
                lambda prompt: (s.set.prompt(prompt), PromptConsumerChanged()),
                lambda: (s, PromptConsumerUnhandled(update.char)),
            ))
        return prompt_state_fork(
            lambda: NS.apply(apply_char),
            lambda: NS.pure(PromptConsumerUnhandled(update.char)),
        )

    def consumer(self, a: PromptUpdateConsumer[B]) -> NS[InputState[A, B], PromptConsumerUpdate[B]]:
        return NS.pure(PromptConsumerLocal(a.data))


@do(NS[InputResources[A, B], None])
def process_prompt_update(process: PromptConsumer, action: PromptUpdate[B]) -> Do:
    consumer = yield process_prompt_update_char.match(action).zoom(lens.state)
    yield prompt_if_echoing(redraw_prompt).zoom(lens.state)
    prompt_action = yield process(consumer).zoom(lens.state)
    yield execute_prompt_action.match(prompt_action)


def update_prompt(process: PromptConsumer) -> Callable[[List[PromptUpdate[B]]], NS[InputResources[A, B], None]]:
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


@do(NvimIO[A])
def prompt(process: PromptConsumer, initial: A, start_insert: bool) -> Do:
    log.debug(f'running prompt with {initial}')
    state = PromptEcho() if start_insert else PromptPassthrough()
    res = InputResources.cons(
        InputState.cons(initial, state=state),
        update_prompt(process),
    )
    input_thread = yield N.fork(input_loop, res)
    result = yield intercept_interrupt(res.inputs, res.stop, res, start_prompt_loop().run_s(res))
    yield N.from_io(stop_prompt(res.inputs, res.stop))
    yield N.simple(input_thread.join)
    return result.state.data


__all__ = ('prompt', 'prompt_state_fork', 'prompt_state_fork_strict', 'prompt_if_echoing',)
