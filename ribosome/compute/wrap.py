from typing import TypeVar, Type, Generic, Callable, Any

from amino.case import Case

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
M = TypeVar('M')
R = TypeVar('R')
S = TypeVar('S', bound=Settings)
CC = TypeVar('CC')
C = TypeVar('C')
PS = PluginState[S, D, CC]


class zoom_main_data(
        Generic[S, D, CC, M],
        Case[MainDataProgType, Callable[[PS], M]],
        alg=MainDataProgType,
):

    def plain_main_data_prog_type(self, tpe: PlainMainDataProgType[M]) -> Callable[[PS], D]:
        return lambda a: a.data

    def internal_main_data_prog_type(self, tpe: InternalMainDataProgType[S, D, CC]) -> Callable[[PS], PS]:
        return lambda a: a


class pick_main_data(
        Generic[S, D, CC, M],
        Case[MainDataProgType[M], Callable[[PS, M], PS]],
        alg=MainDataProgType,
):

    def plain_main_data_prog_type(self, tpe: PlainMainDataProgType[M]) -> Callable[[PS, D], PS]:
        return lambda ps, data: ps.set.data(data)

    def internal_main_data_prog_type(self, tpe: InternalMainDataProgType[S, D, CC]) -> Callable[[PS, PS], PS]:
        return lambda ps, data: data


# TODO optimize
def data_for_type(ps: PluginState[S, D, CC], tpe: Type[C]) -> C:
    return ps.data_by_type(tpe)


class wrap_affiliation(
        Generic[C, S, D, CC, M],
        Case[AffiliationProgType, Callable[[PluginState[S, D, CC]], C]],
        alg=AffiliationProgType,
):

    def root_prog_type(self, tpe: RootProgType[M]) -> Callable[[PluginState[S, D, CC]], M]:
        return zoom_main_data.match(tpe.main)

    def component_prog_type(self, tpe: ComponentProgType[C, D]) -> Callable[[PS], ComponentData[M, Any]]:
        inner: Callable[[PluginState[S, D, CC]], M] = zoom_main_data.match(tpe.main)
        def wrap(ps: PluginState[S, D, CC]) -> ComponentData[M, Any]:
            return ComponentData(inner(ps), data_for_type(ps, tpe.comp))
        return wrap


class unwrap_affiliation(
        Generic[C, S, D, CC, M],
        Case[AffiliationProgType[M, C], Callable[[PS, C], PS]],
        alg=AffiliationProgType,
):

    def root_prog_type(self, tpe: RootProgType[M]) -> Callable[[PS, M], PS]:
        return pick_main_data.match(tpe.main)

    def component_prog_type(self, tpe: ComponentProgType[M, C]) -> Callable[[PS, ComponentData[M, Any]], PS]:
        inner: Callable[[PS, M], PS] = pick_main_data.match(tpe.main)
        def unwrap(ps: PS, data: ComponentData[M, Any]) -> PS:
            ps1 = inner(ps, data.main)
            return ps1.update_component_data(tpe.comp, data.comp)
        return unwrap


class wrap_resources(
        Generic[C, S, D, CC, M, R],
        Case[StateProgType[M, C, R], Callable[[PluginState[S, D, CC]], R]],
        alg=StateProgType,
):

    def resources_state_prog_type(self, tpe: ResourcesStateProgType[M, C, S, D, CC]
                                  ) -> Callable[[PS], Resources[S, C, CC]]:
        inner: Callable[[PluginState[S, D, CC]], C] = wrap_affiliation.match(tpe.affiliation)
        return lambda ps: ps.resources_with(inner(ps))

    def plain_state_prog_type(self, tpe: PlainStateProgType[M, C]) -> Callable[[PS], C]:
        return wrap_affiliation.match(tpe.affiliation)


class unwrap_resources(
        Generic[C, S, D, CC, M, R],
        Case[StateProgType[M, C, R], Callable[[PluginState[S, D, CC], R], PluginState[S, D, CC]]],
        alg=StateProgType,
):

    def resources_state_prog_type(self, tpe: ResourcesStateProgType[M, C, S, D, CC]
                                  ) -> Callable[[PS, Resources[S, C, CC]], PS]:
        inner: Callable[[PS, C], PS] = unwrap_affiliation.match(tpe.affiliation)
        def unwrap(ps: PS, res_wrapped: Resources[S, C, CC]) -> PS:
            return inner(ps, res_wrapped.data)
        return unwrap

    def plain_state_prog_type(self, tpe: PlainStateProgType[M, C]) -> Callable[[PS, R], PS]:
        return unwrap_affiliation.match(tpe.affiliation)


class prog_wrappers(
        Generic[M, C, R, S, D, CC],
        Case[ProgType[M, C, R], ProgWrappers[PS, R]],
        alg=ProgType,
):

    def unknown_prog_type(self, tpe: UnknownProgType[M, C]) -> ProgWrappers[PS, R]:
        raise Exception('unknown prog type')

    def state_prog(self, tpe: StateProg[M, C, R]) -> ProgWrappers[PS, R]:
        return ProgWrappers(wrap_resources.match(tpe.tpe), unwrap_resources.match(tpe.tpe))


__all__ = ('prog_wrappers',)
