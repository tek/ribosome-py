from typing import Generic, TypeVar, Type

from lenses import UnboundLens

from amino import Dat

from ribosome.config.settings import Settings
from ribosome.data.plugin_state import PluginState

S = TypeVar('S', bound=Settings)
D = TypeVar('D')
CC = TypeVar('CC')
C = TypeVar('C')


class Ribosome(Generic[S, D, CC, C], Dat['Ribosome[S, D, CC, C]']):

    def __init__(
            self,
            state: PluginState[S, D, CC],
            comp_type: Type[C],
            comp_lens: UnboundLens['Ribosome[S, D, CC, C]', 'Ribosome[S, D, CC, C]', C, C],
    ) -> None:
        self.state = state
        self.comp_type = comp_type
        self.comp_lens = comp_lens


__all__ = ('Ribosome',)
