from typing import GenericMeta, TypeVar, Callable

from ribosome.nvim.io.state import NS
from ribosome.config.settings import Settings
from ribosome.compute.ribosome import Ribosome
from ribosome.config.setting import Setting
from ribosome.nvim.io.compute import NvimIO

A = TypeVar('A')
S = TypeVar('S', bound=Settings)
D = TypeVar('D')
CC = TypeVar('CC')
C = TypeVar('C')


class RMeta(GenericMeta):
    pass


class Ribo(metaclass=RMeta):

    @classmethod
    def setting(self, attr: Callable[[S], Setting[A]]) -> NS[Ribosome[S, D, CC, C], A]:
        def get(rib: Ribosome[S, D, CC, C]) -> NvimIO[A]:
            return attr(rib.state.basic.settings).value_or_default
        return NS.inspect_f(get)

    @classmethod
    def settings(self) -> NS[Ribosome[S, D, CC, C], S]:
        return NS.inspect(lambda a: a.ps.settings)

    @classmethod
    def comp(self) -> NS[Ribosome[S, D, CC, C], C]:
        return NS.inspect(lambda a: a.comp_lens.get()(a))

    @classmethod
    def modify_comp(self, f: Callable[[C], C]) -> NS[Ribosome[S, D, CC, C], None]:
        return NS.modify(lambda a: a.comp_lens.modify(f)(a))


__all__ = ('Ribosome', 'Ribo')
