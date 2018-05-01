from typing import TypeVar, Type, Generic, Callable, Any

from amino.case import Case

from lenses import UnboundLens  # type: ignore
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
PS = PluginState[D, CC]  # type: ignore


class zoom_main_data(
        Generic[D, CC, M],
        Case[MainDataProgType, Callable[[PS], M]],
        alg=MainDataProgType,
):

    def plain_main_data_prog_type(self, tpe: PlainMainDataProgType[M]) -> Callable[[PS], D]:
        return lambda a: a.data

    def internal_main_data_prog_type(self, tpe: InternalMainDataProgType[D, CC]) -> Callable[[PS], PS]:
        return lambda a: a


class pick_main_data(
        Generic[D, CC, M],
        Case[MainDataProgType[M], Callable[[PS, M], PS]],
        alg=MainDataProgType,
):

    def plain_main_data_prog_type(self, tpe: PlainMainDataProgType[M]) -> Callable[[PS, D], PS]:
        return lambda ps, data: ps.set.data(data)

    def internal_main_data_prog_type(self, tpe: InternalMainDataProgType[D, CC]) -> Callable[[PS, PS], PS]:
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

    def component_prog_type(self, tpe: ComponentProgType[C, D]) -> Callable[[PS], ComponentData[M, Any]]:
        inner: Callable[[PluginState[D, CC]], M] = zoom_main_data.match(tpe.main)
        def wrap(ps: PluginState[D, CC]) -> ComponentData[M, Any]:
            return ComponentData(inner(ps), data_for_type(ps, tpe.comp))
        return wrap


class unwrap_affiliation(
        Generic[C, D, CC, M],
        Case[AffiliationProgType[M, C], Callable[[PS, C], PS]],
        alg=AffiliationProgType,
):

    def root_prog_type(self, tpe: RootProgType[M]) -> Callable[[PS, M], PS]:
        return pick_main_data.match(tpe.main)

    def component_prog_type(self, tpe: ComponentProgType[M, C]) -> Callable[[PS, ComponentData[M, Any]], PS]:
        inner: Callable[[PS, M], PS] = pick_main_data.match(tpe.main)
        def unwrap(ps: PS, data: ComponentData[M, Any]) -> PS:
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

    def resources_state_prog_type(self, tpe: ResourcesStateProgType[M, C, D, CC]) -> Callable[[PS], Resources[D, CC]]:
        inner: Callable[[PluginState[D, CC]], C] = wrap_affiliation.match(tpe.affiliation)
        return lambda ps: ps.resources_with(inner(ps))

    def plain_state_prog_type(self, tpe: PlainStateProgType[M, C]) -> Callable[[PS], C]:
        return wrap_affiliation.match(tpe.affiliation)

    def wrap_ribosome(self, tpe: RibosomeStateProgType[D, CC, C]) -> Callable[[PS], Ribosome[D, CC, C]]:
        comp_lens = ribosome_comp_lens(tpe.comp)
        def wrap(ps: PS) -> Ribosome[D, CC, C]:
            return Ribosome(ps, tpe.comp, comp_lens)
        return wrap


class unwrap_resources(
        Generic[C, D, CC, M, R],
        Case[StateProgType[M, C, R], Callable[[PluginState[D, CC], R], PluginState[D, CC]]],
        alg=StateProgType,
):

    def resources_state_prog_type(self, tpe: ResourcesStateProgType[M, C, D, CC]
                                  ) -> Callable[[PS, Resources[D, CC]], PS]:
        inner: Callable[[PS, C], PS] = unwrap_affiliation.match(tpe.affiliation)
        def unwrap(ps: PS, res_wrapped: Resources[C, CC]) -> PS:
            return inner(ps, res_wrapped.data)
        return unwrap

    def plain_state_prog_type(self, tpe: PlainStateProgType[M, C]) -> Callable[[PS, R], PS]:
        return unwrap_affiliation.match(tpe.affiliation)

    def unwrap_ribosome(self, tpe: RibosomeStateProgType[D, CC, C]) -> Callable[[PS, Ribosome[D, CC, C]], PS]:
        def wrap(ps: PS, ribo: Ribosome[D, CC, C]) -> PS:
            return ribo.state
        return wrap


class prog_wrappers(
        Generic[M, C, R, D, CC],
        Case[ProgType[M, C, R], ProgWrappers[PS, R]],
        alg=ProgType,
):

    def unknown_prog_type(self, tpe: UnknownProgType[M, C]) -> ProgWrappers[PS, R]:
        return Left('not an `NvimIOState`')

    def state_prog(self, tpe: StateProg[M, C, R, A]) -> ProgWrappers[PS, R]:
        return Right(ProgWrappers(wrap_resources.match(tpe.tpe), unwrap_resources.match(tpe.tpe)))


__all__ = ('prog_wrappers',)
