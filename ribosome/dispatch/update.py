from typing import TypeVar, Tuple

from amino import do, Do, _, __, Map, List, Either, L
from amino.lenses.lens import lens
from amino.state import EitherState
from amino.func import flip

from ribosome.nvim.io import NS
from ribosome.plugin_state import (PluginState, DispatchAffiliation, RootDispatch, ComponentDispatch, Syncs, Asyncs,
                                   AffiliatedDispatch)
from ribosome.dispatch.resolve import ComponentResolver
from ribosome.config.config import Config
from ribosome.dispatch.data import DispatchAsync, SendMessage, Trans, Dispatch
from ribosome.request.handler.handler import RequestHandler, RequestHandlers
from ribosome.dispatch.component import Components, Component
from ribosome.request.rpc import define_handlers
from ribosome.config.settings import Settings

D = TypeVar('D')
DP = TypeVar('DP', bound=Dispatch)
S = TypeVar('S', bound=Settings)
CC = TypeVar('CC')


def choose_dispatch(handler: RequestHandler) -> DispatchAsync:
    tpe = (
        SendMessage
        if handler.msg else
        Trans
    )
    return tpe(handler)


def request_handlers_dispatches(handlers: RequestHandlers) -> List[DispatchAffiliation]:
    return handlers.handlers.v.map(choose_dispatch)


def config_dispatches(config: Config) -> List[AffiliatedDispatch[Dispatch]]:
    return request_handlers_dispatches(config.request_handlers) / L(AffiliatedDispatch)(_, RootDispatch())


def component_dispatches(component: Component) -> List[AffiliatedDispatch[DispatchAsync]]:
    return (
        request_handlers_dispatches(component.request_handlers) /
        L(AffiliatedDispatch)(_, ComponentDispatch(component))
    )


def dispatches(state: PluginState[S, D, CC]) -> Tuple[Syncs, Asyncs]:
    config = state.config
    cfg_dispatches = config_dispatches(config)
    compo_dispatches = state.components.all // component_dispatches
    dispatches = compo_dispatches + cfg_dispatches
    sync_dispatch, async_dispatch = dispatches.filter(_.sync), dispatches.filter(_.async)
    rpc_method = lambda d: d.dispatch.spec(config.name, config.prefix).rpc_method
    return (
        Map(sync_dispatch.apzip(rpc_method).map2(flip)),
        async_dispatch.group_by(rpc_method),
    )


@do(EitherState[PluginState[S, D, CC], None])
def update_components(from_user: Either[str, List[str]]) -> Do:
    config = yield EitherState.inspect(_.config)
    components = yield EitherState.lift(ComponentResolver(config, from_user).run)
    yield EitherState.modify(__.copy(components=Components.cons(components, config.component_config_type)))
    sy, asy = yield EitherState.inspect(dispatches)
    yield EitherState.modify(lens.dispatch_config.async_dispatch.set(asy))
    yield EitherState.modify(lens.dispatch_config.sync_dispatch.set(sy))


# TODO finish
@do(NS[PluginState[S, D, CC], None])
def undef_handlers() -> Do:
    handlers = yield NS.inspect(_.dispatch_config.rpc_handlers)
    return handlers


@do(NS[PluginState[S, D, CC], None])
def update_rpc() -> Do:
    config = yield NS.inspect(_.config)
    yield undef_handlers()
    from_user = yield NS.lift(config.settings.components.value)
    yield update_components(from_user).nvim
    specs = yield NS.inspect(_.dispatch_config.distinct_specs)
    handlers = yield NS.lift(define_handlers(specs, config.name))
    yield NS.modify(lens.dispatch_config.rpc_handlers.set(handlers))

__all__ = ('update_rpc',)
