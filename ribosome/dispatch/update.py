from typing import TypeVar

from amino import do, Do, _, __, List, Either, L
from amino.lenses.lens import lens
from amino.state import EitherState

from ribosome.nvim.io.state import NS
from ribosome.data.plugin_state import PluginState, Programs, handler_spec
from ribosome.dispatch.resolve import ComponentResolver
from ribosome.request.handler.handler import RequestHandler, RequestHandlers
from ribosome.config.component import Components, Component
from ribosome.request.rpc import define_handlers, RpcHandlerSpec
from ribosome.config.settings import Settings
from ribosome.compute.prog import Program
from ribosome.request.handler.method import RpcMethod
from ribosome.util.setting import setting_ps_e

CC = TypeVar('CC')
D = TypeVar('D')
Meth = TypeVar('Meth', bound=RpcMethod)
P = TypeVar('P')
S = TypeVar('S', bound=Settings)


def request_handlers_dispatches(handlers: RequestHandlers) -> List[Program]:
    return handlers.handlers.v


def component_dispatches(component: Component) -> List[Program]:
    return request_handlers_dispatches(component.request_handlers)


def rpc_method(name: str, prefix: str) -> str:
    def rpc_method(handler: RequestHandler) -> str:
        return handler_spec(handler, name, prefix).rpc_method
    return rpc_method


def dispatches(state: PluginState[S, D, CC]) -> Programs:
    cfg_dispatches = request_handlers_dispatches(state.request_handlers)
    compo_dispatches = state.components.all // component_dispatches
    dispatch = compo_dispatches + cfg_dispatches
    method = rpc_method(state.basic.name, state.basic.prefix)
    return dispatch.group_by(method)


@do(EitherState[PluginState[S, D, CC], None])
def update_components(from_user: Either[str, List[str]]) -> Do:
    name = yield EitherState.inspect(_.basic.name)
    components_map = yield EitherState.inspect(_.comp.available)
    core_components = yield EitherState.inspect(_.basic.core_components)
    default_components = yield EitherState.inspect(_.basic.default_components)
    resolver = ComponentResolver(name, components_map, core_components, default_components, from_user)
    components = yield EitherState.lift(resolver.run())
    yield EitherState.modify(__.copy(components=Components.cons(components)))
    dispatch = yield EitherState.inspect(dispatches)
    yield EitherState.modify(lens.programs.set(dispatch))


@do(NS[PluginState[S, D, CC], None])
def undef_handler(handler: RpcHandlerSpec) -> Do:
    yield NS.unit


# TODO finish
@do(NS[PluginState[S, D, CC], None])
def undef_handlers() -> Do:
    handlers = yield NS.inspect(_.rpc_handlers)
    yield handlers.traverse(undef_handler, NS)


@do(NS[PluginState[S, D, CC], None])
def def_handlers() -> Do:
    name = yield NS.inspect(_.basic.name)
    specs = yield NS.inspect(_.distinct_specs)
    handlers = yield NS.lift(define_handlers(specs, name))
    yield NS.modify(lens.rpc_handlers.set(handlers))


@do(NS[PluginState[S, D, CC], None])
def init_rpc() -> Do:
    from_user = yield setting_ps_e(_.components)
    yield update_components(from_user).nvim
    yield def_handlers()


__all__ = ('init_rpc', 'undef_handlers', 'def_handlers', 'dispatches')
