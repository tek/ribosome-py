import abc
from typing import TypeVar, Callable, Any, Generic

from amino.tc.base import TypeClass, tc_prop
from amino import Either, __, IO, Maybe
from amino.state import tcs, StateT, State, EitherState
from amino.func import CallByName
from amino.util.trace import cframe

from ribosome.nvim.api.data import NvimApi
from ribosome.nvim.io import NvimIO

A = TypeVar('A')
S = TypeVar('S')


class NvimIOState(Generic[S, A], StateT[NvimIO, S, A], tpe=NvimIO):

    @staticmethod
    def io(f: Callable[[NvimApi], A]) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(NvimIO.delay(f))

    @staticmethod
    def delay(f: Callable[[NvimApi], A]) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(NvimIO.delay(f))

    @staticmethod
    def suspend(f: Callable[[NvimApi], NvimIO[A]]) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(NvimIO.suspend(f))

    @staticmethod
    def from_io(io: IO[A]) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(NvimIO.wrap_either(lambda v: io.attempt))

    @staticmethod
    def from_id(st: State[S, A]) -> 'NvimIOState[S, A]':
        return st.transform_f(NvimIOState, lambda s: NvimIO.pure(s.value))

    @staticmethod
    def from_maybe(a: Maybe[A], err: CallByName) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(NvimIO.from_maybe(a, err))

    @staticmethod
    def from_either(e: Either[str, A]) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(NvimIO.from_either(e))

    @staticmethod
    def from_either_state(st: EitherState[S, A]) -> 'NvimIOState[S, A]':
        return st.transform_f(NvimIOState, lambda s: NvimIO.from_either(s))

    @staticmethod
    def failed(e: str) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(NvimIO.failed(e))

    @staticmethod
    def error(e: str) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(NvimIO.error(e))

    @staticmethod
    def inspect_maybe(f: Callable[[S], Either[str, A]], err: CallByName) -> 'NvimIOState[S, A]':
        frame = cframe()
        return NvimIOState.inspect_f(lambda s: NvimIO.from_maybe(f(s), err, frame))

    @staticmethod
    def inspect_either(f: Callable[[S], Either[str, A]]) -> 'NvimIOState[S, A]':
        frame = cframe()
        return NvimIOState.inspect_f(lambda s: NvimIO.from_either(f(s), frame))

    @staticmethod
    def call(name: str, *args: Any, **kw: Any) -> 'NvimIOState[S, A]':
        return NS.delay(__.call(name, *args, **kw))


tcs(NvimIO, NvimIOState)  # type: ignore

NS = NvimIOState


class ToNvimIOState(TypeClass):

    @abc.abstractproperty
    def nvim(self) -> NS:
        ...


class IdStateToNvimIOState(ToNvimIOState, tpe=State):

    @tc_prop
    def nvim(self, fa: State[S, A]) -> NS:
        return NvimIOState.from_id(fa)


class EitherStateToNvimIOState(ToNvimIOState, tpe=EitherState):

    @tc_prop
    def nvim(self, fa: EitherState[S, A]) -> NS:
        return NvimIOState.from_either_state(fa)


__all__ = ('NvimIOState', 'NS')
