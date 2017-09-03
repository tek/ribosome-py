from typing import TypeVar, Callable, Any, Generic

from amino.tc.base import ImplicitInstances, F
from amino.lazy import lazy
from amino.tc.monad import Monad
from amino import Either, Right, Left, __

from ribosome.nvim.components import NvimComponent

A = TypeVar('A')
B = TypeVar('B')


class NvimIOInstances(ImplicitInstances):

    @lazy
    def _instances(self) -> 'amino.map.Map':
        from amino.map import Map
        return Map({Monad: NvimIOMonad()})


class NvimIO(Generic[A], F[A], implicits=True, imp_mod='ribosome.nvim.io', imp_cls='NvimIOInstances'):

    @staticmethod
    def wrap_either(f: Callable[[NvimComponent], A]) -> 'NvimIO[A]':
        return NvimIO(lambda a: f(a).get_or_raise)

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
    def failed(msg: str) -> 'NvimIO[A]':
        def fail() -> A:
            raise Exception(msg)
        return NvimIO(lambda v: fail())

    def __init__(self, run: Callable[[NvimComponent], A]) -> None:
        self.run = run

    def attempt(self, vim: NvimComponent) -> Either[Exception, A]:
        try:
            return Right(self.run(vim))
        except Exception as e:
            return Left(e)

    unsafe_perform_io = attempt

    def effect(self, f: Callable[[A], Any]) -> 'NvimIO[A]':
        def wrap(v: NvimComponent) -> A:
            ret = self.run(v)
            f(ret)
            return ret
        return NvimIO(wrap)

    __mod__ = effect


class NvimIOMonad(Monad[NvimIO]):

    def pure(self, a: A) -> NvimIO[A]:
        return NvimIO.pure(a)

    def flat_map(self, fa: NvimIO[A], f: Callable[[A], NvimIO[B]]) -> NvimIO[B]:
        g = lambda v: f(fa.run(v)).run(v)
        return NvimIO(g)

    def map(self, fa: NvimIO[A], f: Callable[[A], B]) -> NvimIO[B]:
        return NvimIO(lambda a: f(fa.run(a)))

__all__ = ('NvimIO',)
