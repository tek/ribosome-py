from typing import TypeVar, Callable

from amino.tc.monad import Monad
from amino.tc.base import ImplicitInstances, tc_prop
from amino.lazy import lazy
from amino import Map
from amino.tc.monoid import Monoid

from ribosome.nvim.io.compute import NvimIO, flat_map_nvim_io, NvimIOPure

A = TypeVar('A')
B = TypeVar('B')


class NvimIOInstances(ImplicitInstances):

    @lazy
    def _instances(self) -> Map:
        return Map({
            Monad: NvimIOMonad(),
            Monoid: NvimIOMonoid(),
        })


class NvimIOMonad(Monad):

    def pure(self, a: A) -> NvimIO[A]:
        return NvimIOPure(a)

    def flat_map(self, fa: NvimIO[A], f: Callable[[A], NvimIO[B]]) -> NvimIO[B]:
        return flat_map_nvim_io(f)(fa)


class NvimIOMonoid(Monoid):

    @tc_prop
    def empty(self) -> NvimIO[None]:
        return NvimIOPure(None)

    def combine(self, a: NvimIO[A], b: NvimIO[A]) -> NvimIO[A]:
        return a.flat_map(b)


__all__ = ('NvimIOInstances', 'NvimIOMonad', 'NvimIOMonoid',)
