from __future__ import annotations
from typing import Generic, TypeVar, Type

from lenses import UnboundLens

from amino import Dat

from ribosome.data.plugin_state import PluginState

D = TypeVar('D')
CC = TypeVar('CC')
C = TypeVar('C')


class Ribosome(Generic[D, CC, C], Dat['Ribosome[D, CC, C]']):

    def __init__(
            self,
            state: PluginState[D, CC],
            comp_type: Type[C],
            comp_lens: UnboundLens['Ribosome[D, CC, C]', 'Ribosome[D, CC, C]', C, C],
    ) -> None:
        self.state = state
        self.comp_type = comp_type
        self.comp_lens = comp_lens


__all__ = ('Ribosome',)
