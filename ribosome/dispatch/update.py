from typing import TypeVar

from amino import do, Do, _, __, List, Either, L
from amino.lenses.lens import lens
from amino.state import EitherState

from ribosome.nvim.io.state import NS
from ribosome.plugin_state import PluginState, Programs
from ribosome.dispatch.resolve import ComponentResolver
from ribosome.config.config import Config
from ribosome.request.handler.handler import RequestHandler, RequestHandlers
from ribosome.config.component import Components, Component
from ribosome.request.rpc import define_handlers, RpcHandlerSpec
from ribosome.config.settings import Settings
from ribosome.compute.prog import Program

D = TypeVar('D')
S = TypeVar('S', bound=Settings)
CC = TypeVar('CC')


def request_handlers_dispatches(handlers: RequestHandlers) -> List[Program]:
    return handlers.handlers.v


def config_dispatches(config: Config) -> List[Program]:
    return request_handlers_dispatches(config.request_handlers)


def component_dispatches(component: Component) -> List[Program]:
    return request_handlers_dispatches(component.request_handlers)


def dispatches(state: PluginState[S, D, CC]) -> Programs:
    config = state.config
    cfg_dispatches = config_dispatches(config)
    compo_dispatches = state.components.all // component_dispatches
    dispatch = compo_dispatches + cfg_dispatches
    rpc_method = lambda d: d.spec(config.name, config.prefix).rpc_method
    return dispatch.group_by(rpc_method)


@do(EitherState[PluginState[S, D, CC], None])
def update_components(from_user: Either[str, List[str]]) -> Do:
    config = yield EitherState.inspect(_.config)
    components = yield EitherState.lift(ComponentResolver(config, from_user).run)
    yield EitherState.modify(__.copy(components=Components.cons(components, config.component_config_type)))
    dispatch = yield EitherState.inspect(dispatches)
    yield EitherState.modify(lens.dispatch_config.programs.set(dispatch))


@do(NS[PluginState[S, D, CC], None])
def undef_handler(handler: RpcHandlerSpec) -> Do:
    yield NS.unit


# TODO finish
@do(NS[PluginState[S, D, CC], None])
def undef_handlers() -> Do:
    handlers = yield NS.inspect(_.dispatch_config.rpc_handlers)
    yield handlers.traverse(undef_handler, NS)


@do(NS[PluginState[S, D, CC], None])
def def_handlers() -> Do:
    config = yield NS.inspect(_.config)
    specs = yield NS.inspect(_.dispatch_config.distinct_specs)
    handlers = yield NS.lift(define_handlers(specs, config.name))
    yield NS.modify(lens.dispatch_config.rpc_handlers.set(handlers))


@do(NS[PluginState[S, D, CC], None])
def init_rpc() -> Do:
    config = yield NS.inspect(_.config)
    from_user = yield NS.lift(config.settings.components.value)
    yield update_components(from_user).nvim
    yield def_handlers()


__all__ = ('init_rpc', 'undef_handlers', 'def_handlers', 'dispatches')
