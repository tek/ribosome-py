from typing import Callable, TypeVar

from amino import Either, do, Do, Right
from amino.util.tpe import first_type_arg, type_arg, normalize_generic_type, is_subclass, is_subclass
from amino.tc.base import normalize_type

from ribosome.config.resources import Resources
from ribosome.config.component import ComponentData
from ribosome.data.plugin_state import PluginState
from ribosome.compute.tpe_data import (MainDataProgType, InternalMainDataProgType, PlainMainDataProgType,
                                       ComponentProgType, AffiliationProgType, PlainStateProgType,
                                       ResourcesStateProgType, StateProg, ProgType, UnknownProgType, RootProgType,
                                       RibosomeStateProgType)
from ribosome.compute.ribosome import Ribosome
from ribosome.compute.wrap import prog_wrappers
from ribosome.compute.wrap_data import ProgWrappers
from ribosome.nvim.io.state import NS
from ribosome.rpc.args import ParamsSpec

A = TypeVar('A')
P = TypeVar('P')
R = TypeVar('R')


def main_data_prog(data_type: type) -> MainDataProgType:
    return (
        InternalMainDataProgType()
        if is_subclass(data_type, PluginState) else
        PlainMainDataProgType()
    )


@do(Either[str, MainDataProgType])
def component_prog(affiliation_type: type) -> Do:
    tpe = yield first_type_arg(affiliation_type)
    component_data = yield type_arg(affiliation_type, 1)
    return ComponentProgType(main_data_prog(tpe), component_data)


@do(Either[str, AffiliationProgType])
def affiliation_prog(affiliation_type: type) -> Do:
    yield (
        component_prog(affiliation_type)
        if is_subclass(affiliation_type, ComponentData) else
        Right(RootProgType(main_data_prog(affiliation_type)))
    )


@do(Either[str, PlainStateProgType])
def plain_prog(plain_type: type) -> Do:
    affiliation = yield affiliation_prog(plain_type)
    return PlainStateProgType(affiliation)


@do(Either[str, ResourcesStateProgType])
def resources_prog(resources_type: type) -> Do:
    tpe = yield first_type_arg(resources_type)
    affiliation = yield affiliation_prog(tpe)
    return ResourcesStateProgType(affiliation)


@do(Either[str, RibosomeStateProgType])
def ribosome_prog(ribosome_type: type) -> Do:
    tpe = yield type_arg(ribosome_type, 2)
    return RibosomeStateProgType(tpe)


@do(Either[str, StateProg])
def state_prog(state_type: type, return_type: type) -> Do:
    state_prog_type = yield (
        resources_prog(state_type)
        if is_subclass(state_type, Resources) else
        ribosome_prog(state_type)
        if is_subclass(state_type, Ribosome) else
        plain_prog(state_type)
    )
    return StateProg(state_prog_type, return_type)


def analyse_prog_tpe(params: ParamsSpec) -> Either[str, ProgType]:
    return params.state_type.cata(
        lambda a: Right(UnknownProgType()),
        lambda a: state_prog(a, params.return_type),
    )


@do(Either[str, ProgWrappers])
def prog_type(func: Callable[[P], NS[R, A]], params_spec: ParamsSpec) -> Do:
    tpe = yield analyse_prog_tpe(params_spec)
    yield prog_wrappers.match(tpe)


__all__ = ('analyse_prog_tpe', 'prog_type')
