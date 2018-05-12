from typing import TypeVar, Generic

from amino.dat import Dat

from ribosome.config.component import Components

A = TypeVar('A')
D = TypeVar('D')
CC = TypeVar('CC')
G = TypeVar('G')


class Resources(Generic[D, CC], Dat['Resources[D, CC]']):

    def __init__(self, data: D, components: Components[CC]) -> None:
        self.data = data
        self.components = components


__all__ = ('Resources',)
