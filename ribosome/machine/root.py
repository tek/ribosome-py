from typing import Generator, Union, TypeVar, Generic, Type

from ribosome.logging import Logging, ribo_log
from ribosome.nvim import NvimIO
from ribosome import NvimFacade
from ribosome.machine.transitions import Transitions
from ribosome.machine.state import PluginStateMachine
from ribosome.machine.machine import Machine
from ribosome.machine.sub import ComponentMachine, Component
from ribosome.machine.internal import Internal
from ribosome.config import PluginSettings, Config, AutoData

from amino import Try, _, L, Either, List, Left, do, Right, curried, Boolean, Nothing
from amino.do import do

Settings = TypeVar('Settings', bound=PluginSettings)
D = TypeVar('D', bound=AutoData)


class RootMachine(Generic[Settings, D], PluginStateMachine):

    def __init__(self, vim: NvimFacade, config: Config[Settings, D], sub: List[Machine], initial_state: D) -> None:
        self.config = config
        self.initial_state = initial_state
        PluginStateMachine.__init__(self, config.name, vim, sub.cons(ComponentMachine(vim, Internal, 'internal', self)))

    @property
    def init(self) -> D:
        return self.initial_state

    def trans(self, *a, **kw) -> None:
        pass


class ComponentResolver(Logging):

    def __init__(self, config: Config) -> None:
        self.config = config

    @property
    def name(self) -> str:
        return self.config.name

    def find_component(self, name: str) -> Either[List[str], ComponentMachine]:
        mods = List(
            Either.import_module(name),
            Either.import_module(f'{self.name}.components.{name}'),
            Either.import_module(f'{self.name}.plugins.{name}'),
        )
        # TODO .traverse(_.swap).swap
        errors = mods.filter(_.is_left) / _.value
        return mods.find(_.is_right) | Left(errors)

    def inst_component(self, mod):
        return (
            Try(getattr(mod, 'Component'), self.vim, self)
            if hasattr(mod, 'Component')
            else Left('module does not define class `Component`')
        )

    def extra_component(self, name: str, vim: NvimFacade) -> Either[List[str], ComponentMachine]:
        auto = f'{self.config.name}.components.{name}'
        return (
            self.declared_component(name)
            .accum_error_f(lambda: self.component_from_exports(auto))
            .accum_error_f(lambda: self.component_from_exports(name))
            .flat_map(self.inst_auto(name, vim))
        )

    def declared_component(self, name: str) -> Either[List[str], Machine]:
        return (
            self.config.components
            .lift(name)
            .to_either(List(f'no auto component defined for `{name}`'))
        )

    @do(Either[List[str], ComponentMachine])
    def component_from_exports(self, mod: str) -> Generator:
        exports = yield Either.exports(mod).lmap(List)
        yield (
            exports.find(L(Boolean.issubclass)(_, (Component, ComponentMachine)))
            .to_either(f'none of `{mod}.__all__` is a `Component`: {exports}')
            .lmap(List)
        )

    @curried
    def inst_auto(self, name: str, vim: NvimFacade, plug: Union[str, Type]) -> Either[str, ComponentMachine]:
        return (
            Right(ComponentMachine(vim, plug, name, Nothing))
            if isinstance(plug, type) and issubclass(plug, Transitions) else
            Right(plug(vim, name))
            if isinstance(plug, type) and issubclass(plug, ComponentMachine) else
            Left(List(f'invalid tpe for auto component: {plug}'))
        )

    @property
    @do(NvimIO[List[str]])
    def components(self) -> Generator:
        from_user = yield self.config.settings.components.value
        additional = from_user | self.config.default_components
        components = self.config.core_components + additional
        ribo_log.debug(f'starting {self.config} with components {components}')
        yield NvimIO.pure(components)

    def create_components(self, name: str) -> NvimIO[Machine]:
        def report(errs):
            msg = 'invalid {} component module "{}": {}'
            self.log.error(msg.format(self.name, name, errs))
        return NvimIO(
            lambda v:
            (self.find_component(name) // self.inst_component)
            .lmap(List)
            .accum_error_f(lambda: self.extra_component(name, v))
            .leffect(report)
        )

    @property
    @do(NvimIO[List[ComponentMachine]])
    def run(self) -> Generator:
        comp = yield self.components
        sub = yield comp.traverse(self.create_components, NvimIO)
        yield NvimIO.from_either(sub.sequence(Either))


def root_machine(vim: NvimFacade, config: Config[Settings, D], initial_state: D) -> None:
    sub = ComponentResolver(config).run.attempt(vim).get_or_raise()
    return RootMachine(vim, config, sub, initial_state)


__all__ = ('RootMachine', 'root_machine')
