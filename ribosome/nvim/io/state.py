import abc
from typing import TypeVar, Callable, Any, Generic

from amino.tc.base import TypeClass, tc_prop
from amino import Either, __, IO, Maybe
from amino.state import tcs, StateT, State, EitherState
from amino.func import CallByName

from ribosome.nvim.api.data import NvimApi
from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.io.api import N

A = TypeVar('A')
B = TypeVar('B')
S = TypeVar('S')


class NvimIOState(Generic[S, A], StateT[NvimIO, S, A], tpe=NvimIO):

    @staticmethod
    def io(f: Callable[[NvimApi], A]) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(N.delay(f))

    @staticmethod
    def delay(f: Callable[[NvimApi], A]) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(N.delay(f))

    @staticmethod
    def suspend(f: Callable[[NvimApi], NvimIO[A]]) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(N.suspend(f))

    @staticmethod
    def from_io(io: IO[A]) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(N.wrap_either(lambda v: io.attempt))

    @staticmethod
    def from_id(st: State[S, A]) -> 'NvimIOState[S, A]':
        return st.transform_f(NvimIOState, lambda s: N.pure(s.value))

    @staticmethod
    def from_maybe(a: Maybe[B], err: CallByName) -> 'NvimIOState[S, B]':
        return NvimIOState.lift(N.from_maybe(a, err))

    m = from_maybe

    @staticmethod
    def from_either(e: Either[str, A]) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(N.from_either(e))

    e = from_either

    @staticmethod
    def from_either_state(st: EitherState[S, A]) -> 'NvimIOState[S, A]':
        return st.transform_f(NvimIOState, lambda s: N.from_either(s))

    @staticmethod
    def failed(e: str) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(N.failed(e))

    @staticmethod
    def error(e: str) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(N.error(e))

    @staticmethod
    def inspect_maybe(f: Callable[[S], Either[str, A]], err: CallByName) -> 'NvimIOState[S, A]':
        return NvimIOState.inspect_f(lambda s: N.from_maybe(f(s), err))

    @staticmethod
    def inspect_either(f: Callable[[S], Either[str, A]]) -> 'NvimIOState[S, A]':
        return NvimIOState.inspect_f(lambda s: N.from_either(f(s)))

    @staticmethod
    def call(name: str, *args: Any, **kw: Any) -> 'NvimIOState[S, A]':
        return NS.delay(__.call(name, *args, **kw))

    @staticmethod
    def simple(f: Callable[..., A], *a: Any, **kw: Any) -> 'NvimIOState[S, A]':
        return NS.lift(N.simple(f, *a, **kw))

    @staticmethod
    def sleep(duration: float) -> 'NvimIOState[S, A]':
        return NS.lift(N.sleep(duration))


tcs(NvimIO, NvimIOState)

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
