from amino import Either, List, Left, do, Right, curried, Do
from amino.mod import instance_from_module

from ribosome.logging import Logging, ribo_log
from ribosome.config.config import Config
from ribosome.dispatch.component import Component


class ComponentResolver(Logging):

    def __init__(self, config: Config, user_components: Either[str, List[str]]) -> None:
        self.config = config
        self.user_components = user_components

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def run(self) -> Either[str, List[Component]]:
        return self.components.traverse(self.create_components, Either)

    @property
    def components(self) -> List[str]:
        additional = self.user_components | self.config.default_components
        components = self.config.core_components + additional
        ribo_log.debug(f'starting {self.config.name} with components {components}')
        return components

    def create_components(self, name: str) -> Either[str, List[Component]]:
        def report(errs: List[str]):
            msg = 'invalid {} component module "{}": {}'
            self.log.error(msg.format(self.name, name, errs))
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
            self.config.components
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
