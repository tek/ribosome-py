from typing import Iterable

from amino import Lists, Either, do, Do, Maybe, Right, Left

from ribosome.config.resources import Resources
from ribosome.config.component import ComponentData
from ribosome.request.args import ParamsSpec
from ribosome.data.plugin_state import PluginState
from ribosome.compute.tpe_data import (MainDataProgType, InternalMainDataProgType, PlainMainDataProgType,
                                       ComponentProgType, AffiliationProgType, PlainStateProgType,
                                       ResourcesStateProgType, StateProg, ProgType, UnknownProgType, RootProgType,
                                       RibosomeStateProgType)
from ribosome.compute.ribosome import Ribosome


@do(Either[str, type])
def type_arg(tpe: type, index: int) -> Do:
    def error() -> str:
        return f'{tpe} has no type args'
    raw = yield Maybe.getattr(tpe, '__args__').to_either_f(error)
    types = yield Right(Lists.wrap(raw)) if isinstance(raw, Iterable) else Left(error())
    yield types.lift(index).to_either_f(lambda: f'{tpe} has less than {index + 1} args')


def first_type_arg(tpe: type) -> Either[str, type]:
    return type_arg(tpe, 0)


def main_data_trans(data_type: type) -> MainDataProgType:
    return (
        InternalMainDataProgType()
        if issubclass(data_type, PluginState) else
        PlainMainDataProgType()
    )


@do(Either[str, MainDataProgType])
def component_trans(affiliation_type: type) -> Do:
    tpe = yield first_type_arg(affiliation_type)
    component_data = yield type_arg(affiliation_type, 1)
    return ComponentProgType(main_data_trans(tpe), component_data)


@do(Either[str, AffiliationProgType])
def affiliation_trans(affiliation_type: type) -> Do:
    yield (
        component_trans(affiliation_type)
        if issubclass(affiliation_type, ComponentData) else
        Right(RootProgType(main_data_trans(affiliation_type)))
    )


@do(Either[str, PlainStateProgType])
def plain_trans(plain_type: type) -> Do:
    affiliation = yield affiliation_trans(plain_type)
    return PlainStateProgType(affiliation)


@do(Either[str, ResourcesStateProgType])
def resources_trans(resources_type: type) -> Do:
    tpe = yield type_arg(resources_type, 1)
    affiliation = yield affiliation_trans(tpe)
    return ResourcesStateProgType(affiliation)


@do(Either[str, RibosomeStateProgType])
def ribosome_trans(ribosome_type: type) -> Do:
    tpe = yield type_arg(ribosome_type, 3)
    return RibosomeStateProgType(tpe)


@do(Either[str, StateProg])
def state_trans(state_type: type) -> Do:
    state_trans_type = yield (
        resources_trans(state_type)
        if issubclass(state_type, Resources) else
        ribosome_trans(state_type)
        if issubclass(state_type, Ribosome) else
        plain_trans(state_type)
    )
    return StateProg(state_trans_type)


def analyse_prog_tpe(params: ParamsSpec) -> Either[str, ProgType]:
    return params.state_type.cata(
        state_trans,
        lambda: Right(UnknownProgType())
    )


__all__ = ('analyse_prog_tpe')
