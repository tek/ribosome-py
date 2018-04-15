import logging
from typing import TypeVar, Generic, Callable, Any, Type
from uuid import UUID

from amino import Map, List, Nil, Either, _, Maybe, Nothing, __, L
from amino.dat import Dat
from amino.util.string import camelcase

from ribosome.config.component import Component, Components, NoComponentData, ComponentConfig
from ribosome.nvim.io.state import NS
from ribosome.compute.program import Program
from ribosome.request.rpc import RpcHandlerSpec, DefinedHandler
from ribosome.config.settings import Settings
from ribosome.config.resources import Resources
from ribosome.request.handler.handler import RequestHandler, RequestHandlers
from ribosome.request.handler.method import RpcMethod
from ribosome.config.basic_config import BasicConfig
from ribosome.compute.output import ProgIO
from ribosome.compute.prog import Prog
from ribosome.compute.interpret import interpret_io, no_interpreter

A = TypeVar('A')
C = TypeVar('C')
CC = TypeVar('CC')
D = TypeVar('D')
DIO = TypeVar('DIO')
Meth = TypeVar('Meth', bound=RpcMethod)
P = TypeVar('P')
S = TypeVar('S', bound=Settings)
Programs = Map[str, Program]


def handler_spec(handler: RequestHandler[Meth, P], name: str, prefix: str) -> RpcHandlerSpec:
    return RpcHandlerSpec.cons(
        handler.method.spec_type,
        handler.sync,
        handler.vim_cmd_name(name, prefix),
        handler.options,
        handler.method_str,
        True,
    )


# FIXME in order to allow transparent updating of components, the data and config part must be separated
# FIXME using state type as a key won't work if multiple comps have the same type
class PluginState(Generic[S, D, CC], Dat['PluginState[S, D, CC]']):

    @staticmethod
    def cons(
            basic: BasicConfig,
            comp: ComponentConfig,
            request_handlers: RequestHandlers,
            data: D,
            components: List[Component],
            init: Program,
            program_log: List[str]=Nil,
            logger: Program[None]=None,
            log_handler: logging.Handler=None,
            component_data: Map[type, Any]=Map(),
            active_mappings: Map[UUID, Program]=Map(),
            io_executor: Callable[[DIO], NS['PluginState[S, D, CC]', Any]]=None,
            rpc_handlers: List[DefinedHandler]=Nil,
            programs: Programs=Map(),
            io_interpreter: Callable[[ProgIO], Prog]=None,
            custom_io: Callable[[Any], Prog[A]]=None,
    ) -> 'PluginState':
        components = Components.cons(components)
        return PluginState(
            basic,
            comp,
            request_handlers,
            data,
            components,
            init,
            program_log,
            log_handler,
            component_data,
            active_mappings,
            rpc_handlers,
            Maybe.optional(io_executor),
            programs,
            io_interpreter or interpret_io(custom_io or no_interpreter, Maybe.optional(logger)),
        )

    def __init__(
            self,
            basic: BasicConfig,
            comp: ComponentConfig,
            request_handlers: RequestHandlers,
            data: D,
            components: Components,
            init: Program,
            program_log: List[str],
            log_handler: Maybe[logging.Handler],
            component_data: Map[type, Any],
            active_mappings: Map[UUID, Program],
            io_executor: Maybe[Callable[[DIO], NS['PluginState[S, D, CC]', Any]]],
            rpc_handlers: List[DefinedHandler],
            programs: Programs,
            io_interpreter: Callable[[ProgIO], Prog],
    ) -> None:
        self.basic = basic
        self.comp = comp
        self.data = data
        self.components = components
        self.init = init
        self.program_log = program_log
        self.log_handler = log_handler
        self.component_data = component_data
        self.active_mappings = active_mappings
        self.io_executor = io_executor
        self.rpc_handlers = rpc_handlers
        self.programs = programs
        self.request_handlers = request_handlers
        self.io_interpreter = io_interpreter

    def update(self, data: D) -> 'PluginState[S, D, CC]':
        return self.copy(data=data)

    def log_trans(self, trans: str) -> 'PluginState[S, D, CC]':
        return self.append1.program_log(trans)

    def component(self, name: str) -> Either[str, Component]:
        return self.components.by_name(name)

    def ctor_by_type(self, tpe: Type[C]) -> Callable[[], C]:
        return self.components.by_type(tpe) / _.state_ctor | (lambda: NoComponentData)

    def data_by_type(self, tpe: Type[C]) -> C:
        return self.component_data.lift(tpe) | (lambda: self.ctor_by_type(tpe)())

    def data_for(self, component: Component) -> Any:
        return self.component_data.lift(component.state_type) | component.state_ctor

    def data_by_name(self, name: str) -> Either[str, Any]:
        return self.component(name) / self.data_for

    def update_component_data(self, new: C) -> 'PluginState[S, D, CC]':
        return self.mod.component_data(__.cat((type(new), new)))

    def modify_component_data(self, name: str, mod: Callable[[Any], Any]) -> 'PluginState[S, D, CC]':
        comp = self.data_by_name(name)
        return comp / mod / self.update_component_data | self

    def resources_with(self, data: A) -> Resources[S, A, CC]:
        return Resources(data, self.basic.settings, self.components)

    @property
    def resources(self) -> Resources[S, D, CC]:
        return self.resources_with(self.data)

    @property
    def camelcase_name(self) -> str:
        return camelcase(self.basic.name)

    @property
    def specs(self) -> List[RpcHandlerSpec]:
        return self.programs.v.join / L(handler_spec)(_, self.basic.name, self.basic.prefix)

    @property
    def distinct_specs(self) -> List[RpcHandlerSpec]:
        return self.specs.distinct_by(_.rpc_method)


__all__ = ('PluginState',)
