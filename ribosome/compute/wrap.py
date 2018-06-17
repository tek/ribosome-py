from typing import TypeVar, Type, Generic, Callable, Any

from amino.case import Case

from lenses import UnboundLens
from amino import Left, Right
from amino.lenses.lens import lens

from ribosome.data.plugin_state import PluginState
from ribosome.config.component import ComponentData
from ribosome.compute.tpe_data import (ProgType, UnknownProgType, StateProgType, AffiliationProgType, RootProgType,
                                       ComponentProgType, MainDataProgType, PlainMainDataProgType,
                                       InternalMainDataProgType, StateProg, ResourcesStateProgType, PlainStateProgType,
                                       RibosomeStateProgType)
from ribosome.config.resources import Resources
from ribosome.compute.wrap_data import ProgWrappers
from ribosome.compute.ribosome import Ribosome

A = TypeVar('A')
D = TypeVar('D')
M = TypeVar('M')
R = TypeVar('R')
CC = TypeVar('CC')
C = TypeVar('C')
PlS = PluginState[D, CC]  # type: ignore


class zoom_main_data(
        Generic[D, CC, M],
        Case[MainDataProgType, Callable[[PlS], M]],
        alg=MainDataProgType,
):

    def plain_main_data_prog_type(self, tpe: PlainMainDataProgType[M]) -> Callable[[PlS], D]:
        return lambda a: a.data

    def internal_main_data_prog_type(self, tpe: InternalMainDataProgType[D, CC]) -> Callable[[PlS], PlS]:
        return lambda a: a


class pick_main_data(
        Generic[D, CC, M],
        Case[MainDataProgType[M], Callable[[PlS, M], PlS]],
        alg=MainDataProgType,
):

    def plain_main_data_prog_type(self, tpe: PlainMainDataProgType[M]) -> Callable[[PlS, D], PlS]:
        return lambda ps, data: ps.set.data(data)

    def internal_main_data_prog_type(self, tpe: InternalMainDataProgType[D, CC]) -> Callable[[PlS, PlS], PlS]:
        return lambda ps, data: data


# TODO optimize
def data_for_type(ps: PluginState[D, CC], tpe: Type[C]) -> C:
    return ps.data_by_type(tpe)


class wrap_affiliation(
        Generic[C, D, CC, M],
        Case[AffiliationProgType, Callable[[PluginState[D, CC]], C]],
        alg=AffiliationProgType,
):

    def root_prog_type(self, tpe: RootProgType[M]) -> Callable[[PluginState[D, CC]], M]:
        return zoom_main_data.match(tpe.main)

    def component_prog_type(self, tpe: ComponentProgType[C, D]) -> Callable[[PlS], ComponentData[M, Any]]:
        inner: Callable[[PluginState[D, CC]], M] = zoom_main_data.match(tpe.main)
        def wrap(ps: PluginState[D, CC]) -> ComponentData[M, Any]:
            return ComponentData(inner(ps), data_for_type(ps, tpe.comp))
        return wrap


class unwrap_affiliation(
        Generic[C, D, CC, M],
        Case[AffiliationProgType[M, C], Callable[[PlS, C], PlS]],
        alg=AffiliationProgType,
):

    def root_prog_type(self, tpe: RootProgType[M]) -> Callable[[PlS, M], PlS]:
        return pick_main_data.match(tpe.main)

    def component_prog_type(self, tpe: ComponentProgType[M, C]) -> Callable[[PlS, ComponentData[M, Any]], PlS]:
        inner: Callable[[PlS, M], PlS] = pick_main_data.match(tpe.main)
        def unwrap(ps: PlS, data: ComponentData[M, Any]) -> PlS:
            return inner(ps, data.main).update_component_data(data.comp)
        return unwrap


def comp_get(ribo: Ribosome[D, CC, C]) -> C:
    return ribo.state.data_by_type(ribo.comp_type)


def comp_set(ribo: Ribosome[D, CC, C], comp: C) -> Ribosome[D, CC, C]:
    return ribo.mod.state(lambda ps: ps.update_component_data(comp))


def ribosome_comp_lens(tpe: Type[C]) -> UnboundLens[Ribosome[D, CC, C], Ribosome[D, CC, C], C, C]:
    return lens.Lens(comp_get, comp_set)


class wrap_resources(
        Generic[C, D, CC, M, R],
        Case[StateProgType[M, C, R], Callable[[PluginState[D, CC]], R]],
        alg=StateProgType,
):

    def resources_state_prog_type(self, tpe: ResourcesStateProgType[M, C, D, CC]) -> Callable[[PlS], Resources[D, CC]]:
        inner: Callable[[PluginState[D, CC]], C] = wrap_affiliation.match(tpe.affiliation)
        return lambda ps: ps.resources_with(inner(ps))

    def plain_state_prog_type(self, tpe: PlainStateProgType[M, C]) -> Callable[[PlS], C]:
        return wrap_affiliation.match(tpe.affiliation)

    def wrap_ribosome(self, tpe: RibosomeStateProgType[D, CC, C]) -> Callable[[PlS], Ribosome[D, CC, C]]:
        comp_lens = ribosome_comp_lens(tpe.comp)
        def wrap(ps: PlS) -> Ribosome[D, CC, C]:
            return Ribosome(ps, tpe.comp, comp_lens)
        return wrap


class unwrap_resources(
        Generic[C, D, CC, M, R],
        Case[StateProgType[M, C, R], Callable[[PluginState[D, CC], R], PluginState[D, CC]]],
        alg=StateProgType,
):

    def resources_state_prog_type(self, tpe: ResourcesStateProgType[M, C, D, CC]
                                  ) -> Callable[[PlS, Resources[D, CC]], PlS]:
        inner: Callable[[PlS, C], PlS] = unwrap_affiliation.match(tpe.affiliation)
        def unwrap(ps: PlS, res_wrapped: Resources[C, CC]) -> PlS:
            return inner(ps, res_wrapped.data)
        return unwrap

    def plain_state_prog_type(self, tpe: PlainStateProgType[M, C]) -> Callable[[PlS, R], PlS]:
        return unwrap_affiliation.match(tpe.affiliation)

    def unwrap_ribosome(self, tpe: RibosomeStateProgType[D, CC, C]) -> Callable[[PlS, Ribosome[D, CC, C]], PlS]:
        def wrap(ps: PlS, ribo: Ribosome[D, CC, C]) -> PlS:
            return ribo.state
        return wrap


class prog_wrappers(
        Generic[M, C, R, D, CC],
        Case[ProgType[M, C, R], ProgWrappers[PlS, R]],
        alg=ProgType,
):

    def unknown_prog_type(self, tpe: UnknownProgType[M, C]) -> ProgWrappers[PlS, R]:
        return Left('not an `NvimIOState`')

    def state_prog(self, tpe: StateProg[M, C, R, A]) -> ProgWrappers[PlS, R]:
        return Right(ProgWrappers(wrap_resources.match(tpe.tpe), unwrap_resources.match(tpe.tpe)))


__all__ = ('prog_wrappers',)
