from typing import TypeVar, Callable, Any, Generic

from amino.tc.base import ImplicitInstances, Implicits
from amino.lazy import lazy
from amino.tc.monad import Monad
from amino import Either, Right, Left, L, _

from ribosome.nvim.components import NvimComponent

A = TypeVar('A')
B = TypeVar('B')


class NvimIOInstances(ImplicitInstances):

    @lazy
    def _instances(self):
        from amino.map import Map
        return Map({Monad: NvimIOMonad()})


class NvimIO(Generic[A], Implicits, implicits=True, imp_mod='ribosome.nvim.io', imp_cls='NvimIOInstances'):

    def __init__(self, run: Callable[[NvimComponent], A]) -> None:
        self.run = run

    def attempt(self, vim) -> Either[Exception, A]:
        try:
            return Right(self.run(vim))
        except Exception as e:
            return Left(e)

    unsafe_perform_io = attempt

    def effect(self, f: Callable[[A], Any]) -> 'NvimIO[A]':
        def wrap(v):
            ret = self.run(v)
            f(ret)
            return ret
        return NvimIO(wrap)

    __mod__ = effect


class NvimIOMonad(Monad[NvimIO]):

    def pure(self, a: A):
        return NvimIO(lambda v: a)

    def flat_map(self, fa: NvimIO[A], f: Callable[[A], NvimIO[B]]) -> NvimIO[B]:
        g = lambda v: f(fa.run(v)).run(v)
        return NvimIO(g)

    def map(self, fa: NvimIO[A], f: Callable[[A], B]) -> NvimIO[B]:
        return NvimIO(L(fa.run)(_) >> f)

__all__ = ('NvimIO',)
