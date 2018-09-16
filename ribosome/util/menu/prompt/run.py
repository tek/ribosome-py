from typing import Callable, TypeVar
from queue import Queue

from amino import do, Do, IO, List, Nil, Maybe, Try, Nothing, Just
from amino.logging import module_log
from amino.case import Case
from amino.lenses.lens import lens

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.io.api import N
from ribosome.nvim.io.state import NS
from ribosome.util.menu.prompt.data import (Input, InputChar, InputState, InputResources, InputChar, PrintableChar,
                                            SpecialChar, PromptAction, PromptInput, PromptInterrupt, Prompt)
from ribosome.nvim.api.command import nvim_atomic_commands
from ribosome.util.menu.prompt.input import input_loop
from ribosome.util.menu.prompt.interrupt import intercept_interrupt, stop_prompt

log = module_log()
A = TypeVar('A')
B = TypeVar('B')


class process_char(Case[InputChar, NS[InputState[A], None]], alg=InputChar):

    def printable(self, a: PrintableChar) -> NS[InputState[A], None]:
        return NS.modify(lambda s: s.append1.keys(a))

    def special(self, a: SpecialChar) -> NS[InputState[A], None]:
        return NS.modify(lambda s: s.append1.keys(a))


def prompt_fragment(text: str, highlight: Maybe[str]) -> List[str]:
    hl = highlight.get_or_strict('None')
    return List(f'echohl {hl}', f'echon "{text}"')


@do(NS[InputState[A], None])
def redraw_prompt() -> Do:
    prompt, cursor = yield NS.inspect(lambda s: (s.prompt, s.cursor))
    pre, cursor_char, post = prompt.pre, prompt.post[:1], prompt.post[1:]
    cmds = List((pre, Nothing), (cursor_char, Just('RibosomePromptCaret')), (post, Nothing)).flat_map2(prompt_fragment)
    yield NS.lift(nvim_atomic_commands(cmds.cons('redraw')))


class insert_char(Case[InputChar, Prompt], alg=InputChar):

    def __init__(self, prompt: Prompt) -> None:
        self.prompt = prompt

    def printable(self, a: PrintableChar) -> Prompt:
        return self.prompt.copy(cursor=self.prompt.cursor + 1, pre=self.prompt.pre + a.char)

    def special(self, a: SpecialChar) -> Prompt:
        return self.prompt


def update_prompt_text(prompt: Prompt, keys: List[InputChar]) -> Prompt:
    return keys.fold_left(prompt)(lambda z, a: insert_char(z)(a))


def update_prompt(process: Callable[[List[InputChar]], NS[InputState[A], None]]
                  ) -> Callable[[List[InputChar]], NS[InputState[A], None]]:
    @do(NS[InputState[A], None])
    def update_prompt(keys: List[InputChar]) -> Do:
        yield NS.modify(lambda s: s.mod.prompt(lambda a: update_prompt_text(a, keys)))
        yield redraw_prompt()
        yield process(keys)
    return update_prompt


@do(IO[List[Input]])
def dequeue(inputs: Queue) -> Do:
    first = yield IO.delay(inputs.get)
    tail = yield dequeue(inputs) if inputs.qsize() > 0 else IO.pure(List(first))
    return tail.cons(first)


class process_input(Case[PromptAction, Maybe[InputChar]], alg=PromptAction):

    def input(self, a: PromptInput) -> Maybe[InputChar]:
        return Just(a.char)

    def interrupt(self, a: PromptInterrupt) -> Maybe[InputChar]:
        return Nothing


@do(NS[InputResources[A], None])
def prompt_recurse(input: List[InputChar]) -> Do:
    stop = yield NS.inspect(lambda a: a.stop)
    yield input.traverse(process_char.match, NS).zoom(lens.state)
    current = yield NS.apply(lambda s: N.pure((s.set.keys(Nil), s.keys))).zoom(lens.state)
    update = yield NS.inspect(lambda s: s.update)
    yield update(current).zoom(lens.state)
    yield NS.unit if stop.is_set() else prompt_loop()


@do(NS[InputResources[A], None])
def prompt_loop() -> Do:
    inputs = yield NS.inspect(lambda s: s.inputs)
    input = yield NS.from_io(dequeue(inputs))
    chars = input.traverse(process_input.match, Maybe)
    yield chars.cata_strict(prompt_recurse, NS.unit)


@do(NvimIO[A])
def prompt(process: Callable[[List[InputChar]], NS[InputState[A], None]], initial: A) -> Do:
    log.debug(f'running prompt with {initial}')
    res = InputResources.cons(
        InputState.cons(initial),
        update_prompt(process),
    )
    input_thread = yield N.fork(input_loop, res)
    result = yield intercept_interrupt(res.inputs, res.stop, res, prompt_loop().run_s(res))
    yield N.from_io(stop_prompt(res.inputs, res.stop))
    yield N.simple(input_thread.join)
    return result.state.data


__all__ = ('prompt',)
