from typing import TypeVar

from amino import do, Do, _, __, List, Either, Maybe
from amino.lenses.lens import lens
from amino.state import EitherState

from ribosome.nvim.io.state import NS
from ribosome.data.plugin_state import PluginState
from ribosome.config.resolve import ComponentResolver
from ribosome.config.component import Components
from ribosome.nvim.api.command import nvim_command
from ribosome.nvim.io.compute import NvimIO
from ribosome.config import settings
from ribosome.rpc.define import define_rpc, DefinedHandler
from ribosome.rpc.api import RpcProgram

CC = TypeVar('CC')
D = TypeVar('D')
P = TypeVar('P')


def programs(state: PluginState[D, CC]) -> List[RpcProgram]:
    cfg_handlers = state.rpc
    compo_handlers = state.components.all // _.rpc
    return compo_handlers + cfg_handlers


@do(EitherState[PluginState[D, CC], None])
def update_components(requested: Either[str, List[str]]) -> Do:
    name = yield EitherState.inspect(_.basic.name)
    components_map = yield EitherState.inspect(_.comp.available)
    core_components = yield EitherState.inspect(_.basic.core_components)
    default_components = yield EitherState.inspect(_.basic.default_components)
    resolver = ComponentResolver(name, components_map, core_components, default_components, requested)
    components = yield EitherState.lift(resolver.run())
    yield EitherState.modify(__.copy(components=Components.cons(components)))
    progs = yield EitherState.inspect(programs)
    yield EitherState.modify(lens.programs.set(progs))


@do(NvimIO[None])
def undef_handler(dh: DefinedHandler) -> Do:
    yield nvim_command(dh.spec.undef_cmdline)


@do(NS[PluginState[D, CC], None])
def undef_handlers() -> Do:
    handlers = yield NS.inspect(_.rpc_handlers)
    yield NS.lift(handlers.traverse(undef_handler, NvimIO))


@do(NS[PluginState[D, CC], None])
def def_handlers() -> Do:
    name = yield NS.inspect(_.basic.name)
    prefix = yield NS.inspect(_.basic.prefix)
    programs = yield NS.inspect(_.programs)
    handlers = yield NS.lift(define_rpc(programs, name, prefix))
    yield NS.modify(lens.rpc_handlers.set(handlers))


@do(NS[PluginState[D, CC], None])
def init_rpc(requested_components: Maybe[List[str]]) -> Do:
    yield update_components(requested_components).nvim
    yield def_handlers()


@do(NS[PluginState[D, CC], None])
def init_rpc_plugin() -> Do:
    requested_components = yield NS.lift(settings.components.value)
    yield init_rpc(requested_components)


__all__ = ('init_rpc', 'undef_handlers', 'def_handlers', 'programs', 'init_rpc_plugin',)
