from typing import Callable, Tuple, Union, TypeVar, Type, Generic, Any

from amino.case import Case
from amino import ADT
from ribosome.data.plugin_state import PluginState
from ribosome.config.component import ComponentData
from ribosome.compute.tpe_data import (ProgType, UnknownProgType, StateProgType, AffiliationProgType, RootProgType,
                                       ComponentProgType, MainDataProgType, PlainMainDataProgType,
                                       InternalMainDataProgType, StateProg, ResourcesStateProgType,
                                       PlainStateProgType)
from ribosome.config.settings import Settings
from ribosome.config.resources import Resources
from ribosome.compute.wrap_data import ProgWrappers

A = TypeVar('A')
D = TypeVar('D')
S = TypeVar('S', bound=Settings)
CC = TypeVar('CC')
C = TypeVar('C')
TD = Union[PluginState[S, D, CC], Resources[S, D, CC], D]
TT = Union[TD, ComponentData[TD, C]]
AWWrap = Callable[[PluginState[S, D, CC], TD], TT]
AWUnwrap = Callable[[TT], TD]
AWStore = Callable[[TT, PluginState[S, D, CC]], PluginState[S, D, CC]]
AWR = Tuple[AWWrap, AWUnwrap, AWStore]
MDWrap = Callable[[PluginState[S, D, CC]], TD]


class ResourcesWrapping(Generic[S, C, CC, A], ADT['ResourcesWrapping[S, C, CC, A]']):

    def __init__(self, data: A) -> None:
        self.data = data


class ResourcesWrapped(Generic[S, C, CC], ResourcesWrapping[S, C, CC, Resources[S, C, CC]]):
    pass


class ResourcesPlain(Generic[S, C, CC], ResourcesWrapping[S, C, CC, C]):
    pass


class zoom_main_data(Generic[S, D, CC], Case[MainDataProgType, MDWrap], alg=MainDataProgType):

    def plain_main_data_trans_type(self, tpe: PlainMainDataProgType) -> MDWrap:
        def zoom(ps: PluginState[S, D, CC]) -> D:
            return ps.data
        return zoom

    def internal_main_data_trans_type(self, tpe: InternalMainDataProgType) -> MDWrap:
        def zoom(ps: PluginState[S, D, CC]) -> PluginState[S, D, CC]:
            return ps
        return zoom


# TODO optimize
def data_for_type(ps: PluginState[S, D, CC], tpe: Type[C]) -> C:
    return ps.data_by_type(tpe)


class wrap_affiliation(Case[AffiliationProgType, AWWrap], alg=AffiliationProgType):

    def root_trans_type(self, tpe: RootProgType) -> AWWrap:
        inner = zoom_main_data.match(tpe.main)
        def wrap(ps: PluginState[S, D, CC]) -> None:
            return inner(ps)
        return wrap

    def component_trans_type(self, tpe: ComponentProgType) -> AWWrap:
        inner = zoom_main_data.match(tpe.main)
        def wrap(ps: PluginState[S, D, CC]) -> TT:
            return ComponentData(inner(ps), data_for_type(ps, tpe.comp))
        return wrap


class wrap_resources(Case[StateProgType, AWWrap], alg=StateProgType):

    def resources_state_trans_type(self, tpe: ResourcesStateProgType) -> AWWrap:
        inner = wrap_affiliation.match(tpe.affiliation)
        def wrap(ps) -> None:
            return ResourcesWrapped(ps.resources_with(inner(ps)))
        return wrap

    def plain_state_trans_type(self, tpe: PlainStateProgType) -> AWWrap:
        inner = wrap_affiliation.match(tpe.affiliation)
        return lambda ps: ResourcesPlain(inner(ps))


class pick_main_data(Generic[S, D, CC], Case[MainDataProgType, MDWrap], alg=MainDataProgType):

    def plain_main_data_trans_type(self, tpe: PlainMainDataProgType) -> MDWrap:
        def pick(ps: PluginState[S, D, CC], data: D) -> PluginState[S, D, CC]:
            return ps.set.data(data)
        return pick

    def internal_main_data_trans_type(self, tpe: InternalMainDataProgType) -> MDWrap:
        def pick(ps: PluginState[S, D, CC], data: PluginState[S, D, CC]) -> PluginState[S, D, CC]:
            return data
        return pick


class unwrap_affiliation(Generic[C, S, D, CC], Case[AffiliationProgType[C], AWWrap], alg=AffiliationProgType):

    def root_trans_type(self, tpe: RootProgType[C]) -> AWWrap:
        return pick_main_data.match(tpe.main)

    def component_trans_type(self, tpe: ComponentProgType[C]) -> AWWrap:
        inner = pick_main_data.match(tpe.main)
        def unwrap(ps: PluginState[S, D, CC], data: ComponentData) -> PluginState[S, D, CC]:
            ps1 = inner(ps, data.main)
            return ps1.update_component_data(tpe.comp, data.comp)
        return unwrap


class unwrap_resources(Generic[C, S, D, CC], Case[StateProgType[C], AWWrap], alg=StateProgType):

    def resources_state_trans_type(self, tpe: ResourcesStateProgType[C]) -> AWWrap:
        inner = unwrap_affiliation.match(tpe.affiliation)
        def unwrap(ps: PluginState[S, D, CC], res_wrapped: ResourcesWrapped[S, C, CC]) -> PluginState[S, D, CC]:
            return inner(ps, res_wrapped.data.data)
        return unwrap

    def plain_state_trans_type(self, tpe: PlainStateProgType[C]) -> AWWrap:
        inner = unwrap_affiliation.match(tpe.affiliation)
        def unwrap(ps: PluginState[S, D, CC], res_plain: ResourcesPlain[S, C, CC]) -> PluginState[S, D, CC]:
            return inner(ps, res_plain.data)
        return unwrap


class wrap_trans(Generic[C, S, D, CC], Case[ProgType[C], AWWrap], alg=ProgType):

    def unknown_trans_type(self, tpe: UnknownProgType[C]) -> AWWrap:
        return lambda a: a

    def state_trans(self, tpe: StateProg[C]) -> AWWrap:
        return wrap_resources.match(tpe.tpe)


class unwrap_trans(Case[ProgType, AWUnwrap], alg=ProgType):

    def unknown_trans_type(self, tpe: UnknownProgType) -> AWUnwrap:
        return lambda a, b: a

    def state_trans(self, tpe: StateProg) -> AWUnwrap:
        return unwrap_resources.match(tpe.tpe)


def prog_wrappers(tpe: ProgType) -> ProgWrappers:
    return ProgWrappers(wrap_trans.match(tpe), unwrap_trans.match(tpe))


__all__ = ('prog_wrappers',)
