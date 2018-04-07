from amino import ADT


class MainDataProgType(ADT['MainDataProgType']):
    pass


class InternalMainDataProgType(MainDataProgType):
    pass


class PlainMainDataProgType(MainDataProgType):
    pass


class AffiliationProgType(ADT['AffiliationProgType']):
    pass


class RootProgType(AffiliationProgType):

    def __init__(self, main: MainDataProgType) -> None:
        self.main = main


class ComponentProgType(AffiliationProgType):

    def __init__(self, main: MainDataProgType, comp: type) -> None:
        self.main = main
        self.comp = comp


class StateProgType(ADT['StateProgType']):

    def __init__(self, affiliation: AffiliationProgType) -> None:
        self.affiliation = affiliation


class ResourcesStateProgType(StateProgType):
    pass


class PlainStateProgType(StateProgType):
    pass


class ProgType(ADT['ProgType']):
    pass


class UnknownProgType(ProgType):
    pass


class StateProg(ProgType):

    def __init__(self, tpe: StateProgType) -> None:
        self.tpe = tpe


__all__ = ('MainDataProgType', 'InternalMainDataProgType', 'PlainMainDataProgType', 'AffiliationProgType',
           'RootProgType', 'ComponentProgType', 'StateProgType', 'ResourcesStateProgType', 'PlainStateProgType',
           'ProgType', 'UnknownProgType', 'StateProg')
