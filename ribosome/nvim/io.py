from typing import TypeVar, Callable, Any, Generic, Generator
from threading import Thread

from amino.tc.base import ImplicitInstances, F
from amino.lazy import lazy
from amino.tc.monad import Monad
from amino import Either, __, IO, Maybe, Try, Left
from amino.state import tcs, StateT, IdState
from amino.func import CallByName
from amino.do import do

from ribosome.nvim.components import NvimComponent

A = TypeVar('A')
B = TypeVar('B')
S = TypeVar('S')


class NvimIOInstances(ImplicitInstances):

    @lazy
    def _instances(self) -> 'amino.map.Map':
        from amino.map import Map
        return Map({Monad: NvimIOMonad()})


class NvimIO(Generic[A], F[A], implicits=True, imp_mod='ribosome.nvim.io', imp_cls='NvimIOInstances'):

    @staticmethod
    def wrap_either(f: Callable[[NvimComponent], A]) -> 'NvimIO[A]':
        return NvimIO(lambda a: f(a).get_or_raise())

    @staticmethod
    def from_either(e: Either[str, A]) -> 'NvimIO[A]':
        return NvimIO.wrap_either(lambda v: e)

    @staticmethod
    def from_maybe(e: Maybe[A], error: CallByName) -> 'NvimIO[A]':
        return NvimIO.from_either(e.to_either(error))

    @staticmethod
    def cmd_sync(cmdline: str, verbose=False) -> 'NvimIO[str]':
        return NvimIO.wrap_either(__.cmd_sync(cmdline, verbose=verbose))

    @staticmethod
    def cmd(cmdline: str, verbose=False) -> 'NvimIO[str]':
        return NvimIO.wrap_either(__.cmd(cmdline, verbose=verbose))

    @staticmethod
    def call(name: str, *args: Any, **kw: Any) -> 'NvimIO[A]':
        return NvimIO.wrap_either(__.call(name, *args, **kw))

    @staticmethod
    def call_once_defined(name: str, *args: Any, **kw: Any) -> 'NvimIO[A]':
        return NvimIO.wrap_either(__.call_once_defined(name, *args, **kw))

    @staticmethod
    def pure(a: A) -> 'NvimIO[A]':
        return NvimIO(lambda v: a)

    @staticmethod
    def exception(exc: Exception) -> 'NvimIO[A]':
        return NvimIO.from_either(Left(exc))

    @staticmethod
    def failed(msg: str) -> 'NvimIO[A]':
        return NvimIO.exception(Exception(msg))

    @staticmethod
    def from_io(io: IO[A]) -> 'NvimIO[A]':
        return NvimIO(lambda a: io.attempt.get_or_raise())

    @staticmethod
    def fork(f: Callable[[NvimComponent], None]) -> 'NvimIO[None]':
        return NvimIO(lambda v: Thread(target=f, args=(v,)).start())

    def __init__(self, run: Callable[[NvimComponent], A]) -> None:
        self.run = run

    def attempt(self, vim: NvimComponent) -> Either[Exception, A]:
        return Try(self.run, vim)

    def recover(self, f: Callable[[Exception], B]) -> 'NvimIO[B]':
        return NvimIO(self.attempt).map(__.value_or(f))

    @do('NvimIO[A]')
    def ensure(self, f: Callable[[Either[Exception, A]], 'NvimIO[None]']) -> Generator:
        result = yield NvimIO(self.attempt)
        yield f(result)
        yield NvimIO.from_either(result)

    def effect(self, f: Callable[[A], Any]) -> 'NvimIO[A]':
        def wrap(v: NvimComponent) -> A:
            ret = self.run(v)
            f(ret)
            return ret
        return NvimIO(wrap)

    __mod__ = effect

    def error_effect(self, f: Callable[[Exception], None]) -> 'NvimIO[A]':
        return self.ensure(lambda a: NvimIO(lambda v: a.leffect(f)))


class NvimIOMonad(Monad[NvimIO]):

    def pure(self, a: A) -> NvimIO[A]:
        return NvimIO.pure(a)

    def flat_map(self, fa: NvimIO[A], f: Callable[[A], NvimIO[B]]) -> NvimIO[B]:
        return NvimIO(lambda v: f(fa.run(v)).run(v))

    def map(self, fa: NvimIO[A], f: Callable[[A], B]) -> NvimIO[B]:
        return NvimIO(lambda a: f(fa.run(a)))


class NvimIOState(Generic[S, A], StateT[NvimIO, S, A], tpe=NvimIO):

    @staticmethod
    def io(f: Callable[[NvimComponent], A]) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(NvimIO(f))

    @staticmethod
    def from_id(st: IdState[S, A]) -> 'NvimIOState[S, A]':
        return st.transform_f(lambda s: NvimIO.pure(s.value))

tcs(NvimIO, NvimIOState)  # type: ignore

__all__ = ('NvimIO', 'NvimIOState')
