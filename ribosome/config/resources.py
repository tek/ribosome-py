from typing import TypeVar, Generic

from amino.dat import Dat

from ribosome.config.settings import Settings
from ribosome.config.component import Components

A = TypeVar('A')
D = TypeVar('D')
S = TypeVar('S', bound=Settings)
CC = TypeVar('CC')
G = TypeVar('G')


class Resources(Generic[S, D, CC], Dat['Resources[S, D, CC]']):

    def __init__(self, data: D, settings: S, components: Components[D, CC]) -> None:
        self.data = data
        self.settings = settings
        self.components = components


__all__ = ('Resources',)
