import logging
from typing import TypeVar, Generic, Callable, Any, Type
from uuid import UUID

from amino import Map, List, Nil, Either, _, Maybe, __, L
from amino.dat import Dat
from amino.util.string import camelcase

from ribosome.config.component import Component, Components, NoComponentData, ComponentConfig
from ribosome.nvim.io.state import NS
from ribosome.compute.program import Program
from ribosome.request.rpc import RpcHandlerSpec, DefinedHandler
from ribosome.config.resources import Resources
from ribosome.request.handler.handler import RpcProgram
from ribosome.config.basic_config import BasicConfig
from ribosome.compute.output import ProgIO
from ribosome.compute.prog import Prog
from ribosome.compute.interpret import interpret_io, no_interpreter

A = TypeVar('A')
C = TypeVar('C')
CC = TypeVar('CC')
D = TypeVar('D')
DIO = TypeVar('DIO')


# FIXME in order to allow transparent updating of components, the data and config part must be separated
# FIXME using state type as a key won't work if multiple comps have the same type
class PluginState(Generic[D, CC], Dat['PluginState[D, CC]']):

    @staticmethod
    def cons(
            basic: BasicConfig,
            comp: ComponentConfig,
            rpc: List[RpcProgram],
            data: D,
            components: List[Component],
            init: Program,
            program_log: List[str]=Nil,
            logger: Program[None]=None,
            log_handler: logging.Handler=None,
            component_data: Map[type, Any]=Map(),
            active_mappings: Map[UUID, Program]=Map(),
            io_executor: Callable[[DIO], NS['PluginState[D, CC]', Any]]=None,
            rpc_handlers: List[DefinedHandler]=Nil,
            programs: List[Program]=Nil,
            io_interpreter: Callable[[ProgIO], Prog]=None,
            custom_io: Callable[[Any], Prog[A]]=None,
    ) -> 'PluginState':
        return PluginState(
            basic,
            comp,
            rpc,
            data,
            Components.cons(components),
            init,
            program_log,
            Maybe.optional(log_handler),
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
            rpc: List[RpcProgram],
            data: D,
            components: Components,
            init: Program,
            program_log: List[str],
            log_handler: Maybe[logging.Handler],
            component_data: Map[type, Any],
            active_mappings: Map[UUID, Program],
            io_executor: Maybe[Callable[[DIO], NS['PluginState[D, CC]', Any]]],
            rpc_handlers: List[DefinedHandler],
            programs: List[Program],
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
        self.rpc = rpc
        self.io_interpreter = io_interpreter

    def update(self, data: D) -> 'PluginState[D, CC]':
        return self.copy(data=data)

    def log_prog(self, trans: str) -> 'PluginState[D, CC]':
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

    def update_component_data(self, new: C) -> 'PluginState[D, CC]':
        return self.mod.component_data(__.cat((type(new), new)))

    def modify_component_data(self, name: str, mod: Callable[[Any], Any]) -> 'PluginState[D, CC]':
        comp = self.data_by_name(name)
        return comp / mod / self.update_component_data | self

    def resources_with(self, data: A) -> Resources[D, CC]:
        return Resources(data, self.components)

    @property
    def resources(self) -> Resources[D, CC]:
        return self.resources_with(self.data)

    @property
    def camelcase_name(self) -> str:
        return camelcase(self.basic.name)

    def program_by_name(self, name: str) -> Either[str, RpcProgram]:
        return self.programs.find(_.rpc_name == name).to_either(f'no program named `{name}`')


PS = PluginState[D, CC]


__all__ = ('PluginState',)
