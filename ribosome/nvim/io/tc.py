from typing import TypeVar, Callable

from amino.tc.monad import Monad
from amino.tc.base import ImplicitInstances
from amino.lazy import lazy
from amino import Map

from ribosome.nvim.io.compute import NvimIO, flat_map_nvim_io, NvimIOPure

A = TypeVar('A')
B = TypeVar('B')


class NvimIOInstances(ImplicitInstances):

    @lazy
    def _instances(self) -> Map:
        return Map({Monad: NvimIOMonad()})


class NvimIOMonad(Monad):

    def pure(self, a: A) -> NvimIO[A]:
        return NvimIOPure(a)

    def flat_map(self, fa: NvimIO[A], f: Callable[[A], NvimIO[B]]) -> NvimIO[B]:
        return flat_map_nvim_io(f)(fa)


__all__ = ('NvimIOInstances', 'NvimIOMonad')
