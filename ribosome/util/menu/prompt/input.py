from typing import TypeVar, Any, Generic

from amino import do, Do, IO, Right, Either, List, Nil, Maybe, Try, Left
from amino.logging import module_log
from amino.case import Case

from ribosome.nvim.api.function import nvim_call_cons, nvim_call_tpe
from ribosome.nvim.io.compute import NvimIO, NRParams
from ribosome.nvim.io.api import N
from ribosome.util.menu.codes import modifier_codes, special_codes
from ribosome.util.menu.prompt.data import (Input, NoInput, InputResources, InterruptInput, NormalInput, SpecialChar,
                                            PrintableChar, PromptInput)
from ribosome.util.menu.prompt.interrupt import intercept_interrupt, stop_prompt

log = module_log()
A = TypeVar('A')
B = TypeVar('B')


@do(NvimIO[List[str]])
def input_modifiers() -> Do:
    code = yield nvim_call_tpe(int, 'getcharmod')
    return (
        Nil
        if code == 0 else
        modifier_codes.filter2(lambda c, n: code % c == 0).map2(lambda c, n: n)
    )


def parse_special(key: Any) -> Maybe[str]:
    return special_codes.lift(key).map(lambda a: f'<{a}>')


def parse_printable(key: Any) -> Maybe[str]:
    return Try(chr, key).or_else_call(Try, ord, key).to_maybe


def parse_key(key: Any) -> Maybe[Either[str, str]]:
    return (
        parse_special(key).map(Left)
        .or_else_call(lambda: parse_printable(key).map(Right))
    )


@do(NvimIO[Either[str, Input]])
def analyse_key(key: Either[str, str]) -> Do:
    log.debug(f'received prompt input `{key.value}`')
    modifiers = yield input_modifiers()
    return Right(NormalInput(key.cata(lambda a: SpecialChar(a, modifiers), PrintableChar)))


def parse_nonnull_input(data: Any) -> NvimIO[Either[str, Input]]:
    return parse_key(data).map(analyse_key).get_or(Left, f'could not parse input `{data}`')


def parse_input(data: Any) -> NvimIO[Either[str, Input]]:
    return (
        N.pure(Right(NoInput()))
        if data == 0 else
        parse_nonnull_input(data)
    )


def getchar() -> NvimIO[Input]:
    return nvim_call_cons(parse_input, 'getchar', False, params=NRParams.cons(decode=False, timeout=120))


class process_input(Generic[A, B], Case[Input, NvimIO[None]], alg=Input):

    def __init__(self, res: InputResources[A, B]) -> None:
        self.res = res

    @do(NvimIO[None])
    def no(self, a: NoInput) -> Do:
        yield N.sleep(self.res.interval)
        yield input_loop_unsafe(self.res)

    @do(NvimIO[None])
    def normal(self, a: NormalInput) -> Do:
        yield N.from_io(IO.delay(self.res.inputs.put, PromptInput(a.char)))
        yield input_loop_unsafe(self.res)

    def interrupt(self, a: InterruptInput) -> NvimIO[None]:
        return stop_prompt(self.res.inputs, self.res.stop)


@do(NvimIO[None])
def input_step(res: InputResources[A, B]) -> Do:
    input = yield getchar()
    yield process_input(res)(input)


def input_loop_unsafe(res: InputResources[A, B]) -> NvimIO[None]:
    return N.unit if res.stop.is_set() else input_step(res)


def input_loop(res: InputResources[A, B]) -> NvimIO[None]:
    return intercept_interrupt(res.inputs, res.stop, None, input_loop_unsafe(res))


__all__ = ('input_loop',)
