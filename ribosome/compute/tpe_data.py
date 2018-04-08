from typing import TypeVar, Generic, Type

from amino import ADT

from ribosome.data.plugin_state import PluginState
from ribosome.config.resources import Resources
from ribosome.config.component import ComponentData

C = TypeVar('C')
CC = TypeVar('CC')
D = TypeVar('D')
M = TypeVar('M')
R = TypeVar('R')
S = TypeVar('S')


class MainDataProgType(Generic[M], ADT['MainDataProgType[M]']):
    pass


class InternalMainDataProgType(Generic[S, D, CC], MainDataProgType[PluginState[S, D, CC]]):
    pass


class PlainMainDataProgType(Generic[D], MainDataProgType[D]):
    pass


class AffiliationProgType(Generic[M, C], ADT['AffiliationProgType[M, C]']):
    pass


class RootProgType(Generic[M], AffiliationProgType[M, M]):

    def __init__(self, main: MainDataProgType[M]) -> None:
        self.main = main


class ComponentProgType(Generic[M, C], AffiliationProgType[M, ComponentData[M, C]]):

    def __init__(self, main: MainDataProgType[M], comp: Type[C]) -> None:
        self.main = main
        self.comp = comp


class StateProgType(Generic[M, C, R], ADT['StateProgType[M, C, R]']):

    def __init__(self, affiliation: AffiliationProgType[M, C]) -> None:
        self.affiliation = affiliation


class ResourcesStateProgType(Generic[M, C, S, D, CC], StateProgType[M, C, Resources[S, D, CC]]):
    pass


class PlainStateProgType(Generic[M, C], StateProgType[M, C, C]):
    pass


class ProgType(Generic[M, C, R], ADT['ProgType[M, C, R]']):
    pass


class UnknownProgType(Generic[M, C], ProgType[M, C, None]):
    pass


class StateProg(Generic[M, C, R], ProgType[M, C, R]):

    def __init__(self, tpe: StateProgType[M, C, R]) -> None:
        self.tpe = tpe


__all__ = ('MainDataProgType', 'InternalMainDataProgType', 'PlainMainDataProgType', 'AffiliationProgType',
           'RootProgType', 'ComponentProgType', 'StateProgType', 'ResourcesStateProgType', 'PlainStateProgType',
           'ProgType', 'UnknownProgType', 'StateProg')
