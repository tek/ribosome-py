from typing import Generator, Union, Type

from amino import Try, _, L, Either, List, Left, do, Right, curried, Boolean

from ribosome.logging import Logging, ribo_log
from ribosome.nvim import NvimIO
from ribosome import NvimFacade
from ribosome.config import Config
from ribosome.dispatch.component import Component


class ComponentResolver(Logging):

    def __init__(self, config: Config) -> None:
        self.config = config

    @property
    def name(self) -> str:
        return self.config.name

    def find_component(self, name: str) -> Either[List[str], Component]:
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

    def extra_component(self, name: str, vim: NvimFacade) -> Either[List[str], Component]:
        auto = f'{self.config.name}.components.{name}'
        return (
            self.declared_component(name)
            .accum_error_f(lambda: self.component_from_exports(auto))
            .accum_error_f(lambda: self.component_from_exports(name))
            .flat_map(self.inst_auto(name, vim))
        )

    def declared_component(self, name: str) -> Either[List[str], Component]:
        return (
            self.config.components
            .lift(name)
            .to_either(List(f'no auto component defined for `{name}`'))
        )

    @do(Either[List[str], Component])
    def component_from_exports(self, mod: str) -> Generator:
        exports = yield Either.exports(mod).lmap(List)
        yield (
            exports.find(L(Boolean.issubclass)(_, Component))
            .to_either(f'none of `{mod}.__all__` is a `Component`: {exports}')
            .lmap(List)
        )

    @curried
    def inst_auto(self, name: str, vim: NvimFacade, plug: Union[str, Type]) -> Either[str, Component]:
        return (
            Right(plug(name))
            if isinstance(plug, type) and issubclass(plug, Component) else
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

    def create_components(self, name: str) -> NvimIO[List[Component]]:
        def report(errs):
            msg = 'invalid {} component module "{}": {}'
            self.log.error(msg.format(self.name, name, errs))
        return NvimIO.delay(
            lambda v:
            (self.find_component(name) // self.inst_component)
            .lmap(List)
            .accum_error_f(lambda: self.extra_component(name, v))
            .leffect(report)
        )

    @property
    @do(NvimIO[List[Component]])
    def run(self) -> Generator:
        comp = yield self.components
        sub = yield comp.traverse(self.create_components, NvimIO)
        yield NvimIO.from_either(sub.sequence(Either))


__all__ = ('ComponentResolver',)
