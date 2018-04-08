from typing import TypeVar, Generic, Type

from amino import ADT

# from ribosome.data.plugin_state import PluginState

C = TypeVar('C')
CC = TypeVar('CC')
D = TypeVar('D')
S = TypeVar('S')


class MainDataProgType(Generic[D], ADT['MainDataProgType[D]']):
    pass


# class InternalMainDataProgType(Generic[S, D, CC], MainDataProgType[PluginState[S, D, CC]]):
#     pass


class InternalMainDataProgType(Generic[S, D, CC], MainDataProgType):
    pass


class PlainMainDataProgType(MainDataProgType):
    pass


class AffiliationProgType(Generic[C], ADT['AffiliationProgType[C]']):
    pass


class RootProgType(Generic[C], AffiliationProgType[C]):

    def __init__(self, main: MainDataProgType) -> None:
        self.main = main


class ComponentProgType(Generic[C], AffiliationProgType[C]):

    def __init__(self, main: MainDataProgType, comp: Type[C]) -> None:
        self.main = main
        self.comp = comp


class StateProgType(Generic[C], ADT['StateProgType[C]']):

    def __init__(self, affiliation: AffiliationProgType[C]) -> None:
        self.affiliation = affiliation


class ResourcesStateProgType(Generic[C], StateProgType[C]):
    pass


class PlainStateProgType(Generic[C], StateProgType[C]):
    pass


class ProgType(Generic[C], ADT['ProgType[C]']):
    pass


class UnknownProgType(Generic[C], ProgType[C]):
    pass


class StateProg(Generic[C], ProgType[C]):

    def __init__(self, tpe: StateProgType[C]) -> None:
        self.tpe = tpe


__all__ = ('MainDataProgType', 'InternalMainDataProgType', 'PlainMainDataProgType', 'AffiliationProgType',
           'RootProgType', 'ComponentProgType', 'StateProgType', 'ResourcesStateProgType', 'PlainStateProgType',
           'ProgType', 'UnknownProgType', 'StateProg')
