from __future__ import annotations
import logging
from typing import TypeVar, Generic, Callable, Any, Type

from amino import Map, List, Nil, Either, _, Maybe, __
from amino.dat import Dat
from amino.util.string import camelcase
from amino.logging import module_log

from ribosome.config.component import Component, Components, NoComponentData, ComponentConfig
from ribosome.nvim.io.state import NS
from ribosome.compute.program import Program
from ribosome.config.resources import Resources
from ribosome.config.basic_config import BasicConfig
from ribosome.compute.output import ProgIO
from ribosome.compute.prog import Prog
from ribosome.compute.interpret import interpret_io, no_interpreter
from ribosome.rpc.define import ActiveRpcTrigger
from ribosome.rpc.api import RpcProgram

A = TypeVar('A')
C = TypeVar('C')
CC = TypeVar('CC')
CD = TypeVar('CD')
D = TypeVar('D')
DIO = TypeVar('DIO')
log = module_log()


def component_ctor(comp: Component[CD, CC]) -> Callable[[], CD]:
    return comp.state_ctor.get_or_strict(NoComponentData)


def component_ctor_m(comp: Either[str, Component[CD, CC]]) -> Callable[[], CD]:
    return (comp.to_maybe // _.state_ctor).get_or_strict(NoComponentData)


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
            active_mappings: Map[str, Program]=Map(),
            io_executor: Callable[[DIO], NS['PluginState[D, CC]', Any]]=None,
            rpc_triggers: List[ActiveRpcTrigger]=Nil,
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
            rpc_triggers,
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
            active_mappings: Map[str, Program],
            io_executor: Maybe[Callable[[DIO], NS['PluginState[D, CC]', Any]]],
            rpc_triggers: List[ActiveRpcTrigger],
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
        self.rpc_triggers = rpc_triggers
        self.programs = programs
        self.rpc = rpc
        self.io_interpreter = io_interpreter

    def update(self, data: D) -> 'PluginState[D, CC]':
        return self.copy(data=data)

    def log_prog(self, prog: str) -> 'PluginState[D, CC]':
        return self.append1.program_log(prog)

    def component(self, name: str) -> Either[str, Component]:
        return self.components.by_name(name)

    def ctor_by_type(self, tpe: Type[C]) -> Callable[[], C]:
        return component_ctor_m(self.components.by_type(tpe))

    def data_by_type(self, tpe: Type[C]) -> C:
        return self.component_data.lift(tpe) | (lambda: self.ctor_by_type(tpe)())

    def data_for(self, component: Component) -> Any:
        return self.component_data.lift(component.state_type).get_or(component_ctor(component))

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

    def programs_by_name(self, name: str) -> List[RpcProgram]:
        return self.programs.filter(_.rpc_name == name)

    def program_by_name(self, name: str) -> Either[str, RpcProgram]:
        return self.programs_by_name(name).head.to_either(f'no program named `{name}`')


PS = PluginState[D, CC]


__all__ = ('PluginState',)
