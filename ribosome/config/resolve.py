from typing import Any, TypeVar

from amino import Either, List, Left, do, Right, curried, Do, Map, Maybe
from amino.mod import instance_from_module
from amino.logging import module_log

from ribosome.config.component import Component

log = module_log()
D = TypeVar('D')
CC = TypeVar('CC')


class ComponentResolver:

    def __init__(
            self,
            name: str,
            available_components: Map[str, Component[Any, CC]],
            core: List[str],
            default: List[str],
            requested: Maybe[List[str]],
    ) -> None:
        self.name = name
        self.available_components = available_components
        self.core = core
        self.default = default
        self.requested = requested

    def run(self) -> Either[str, List[Component]]:
        return self.components.traverse(self.create_components, Either)

    @property
    def components(self) -> List[str]:
        additional = self.requested | self.default
        components = self.core + additional
        log.debug(f'starting {self.name} with components {components}')
        return components

    def create_components(self, name: str) -> Either[str, List[Component]]:
        def report(errs: List[str]):
            msg = 'invalid {} component module "{}": {}'
            log.error(msg.format(self.name, name, errs))
        return self.resolve_name(name).leffect(report)

    def resolve_name(self, name: str) -> Either[List[str], Component]:
        auto = f'{self.name}.components.{name}'
        return (
            self.declared_component(name)
            .accum_error_f(lambda: self.component_from_exports(auto).lmap(List))
            .accum_error_f(lambda: self.component_from_exports(name).lmap(List))
            .flat_map(self.check_component(name))
        )

    def declared_component(self, name: str) -> Either[List[str], Component]:
        return (
            self.available_components
            .lift(name)
            .to_either(List(f'no auto component defined for `{name}`'))
        )

    @do(Either[str, Component])
    def component_from_exports(self, mod: str) -> Do:
        mod = yield Either.import_module(mod)
        yield instance_from_module(mod, Component)

    @curried
    def check_component(self, name: str, plug: Component) -> Either[str, Component]:
        return (
            Right(plug)
            if isinstance(plug, Component) else
            Left(List(f'invalid type for auto component: {plug}'))
        )


__all__ = ('ComponentResolver',)
