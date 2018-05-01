from typing import TypeVar, Generic, Type, Any

from amino import ADT

from ribosome.data.plugin_state import PluginState
from ribosome.config.resources import Resources
from ribosome.config.component import ComponentData
from ribosome.compute.ribosome import Ribosome

A = TypeVar('A')
C = TypeVar('C')
CC = TypeVar('CC')
D = TypeVar('D')
M = TypeVar('M')
R = TypeVar('R')
S = TypeVar('S')


class MainDataProgType(Generic[M], ADT['MainDataProgType[M]']):
    pass


class InternalMainDataProgType(Generic[D, CC], MainDataProgType[PluginState[D, CC]]):
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
    pass


class ResourcesStateProgType(Generic[M, C, D, CC], StateProgType[M, C, Resources[D, CC]]):

    def __init__(self, affiliation: AffiliationProgType[M, C]) -> None:
        self.affiliation = affiliation


class PlainStateProgType(Generic[M, C], StateProgType[M, C, C]):

    def __init__(self, affiliation: AffiliationProgType[M, C]) -> None:
        self.affiliation = affiliation


class RibosomeStateProgType(Generic[D, CC, C], StateProgType[PluginState[D, CC], C, Ribosome[D, CC, C]]):

    def __init__(self, comp: Type[C]) -> None:
        self.comp = comp


class ProgType(Generic[M, C, R], ADT['ProgType[M, C, R]']):
    pass


class UnknownProgType(Generic[M, C], ProgType[M, C, None]):
    pass


class StateProg(Generic[M, C, R, A], ProgType[M, C, R]):

    def __init__(self, tpe: StateProgType[M, C, R], return_type: A) -> None:
        self.tpe = tpe
        self.return_type = return_type


trivial_state_prog = StateProg(PlainStateProgType(RootProgType(PlainMainDataProgType())), Any)


def ribo_state_prog(comp: Type[C]) -> StateProg[PluginState[D, CC], C, Ribosome[D, CC, C], Any]:
    return StateProg(RibosomeStateProgType(comp), Any)


__all__ = ('MainDataProgType', 'InternalMainDataProgType', 'PlainMainDataProgType', 'AffiliationProgType',
           'RootProgType', 'ComponentProgType', 'StateProgType', 'ResourcesStateProgType', 'PlainStateProgType',
           'ProgType', 'UnknownProgType', 'StateProg', 'RibosomeProg', 'trivial_state_prog', 'ribo_state_prog')
