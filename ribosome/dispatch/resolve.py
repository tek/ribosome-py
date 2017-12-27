from amino import _, Either, List, Left, do, Right, curried, Do
from amino.mod import instance_from_module

from ribosome.logging import Logging, ribo_log
from ribosome.config import Config
from ribosome.dispatch.component import Component


class ComponentResolver(Logging):

    def __init__(self, config: Config, user_components: Either[str, List[str]]) -> None:
        self.config = config
        self.user_components = user_components

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

    def extra_component(self, name: str) -> Either[List[str], Component]:
        auto = f'{self.config.name}.components.{name}'
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

    def components(self) -> List[str]:
        additional = self.user_components | self.config.default_components
        components = self.config.core_components + additional
        ribo_log.debug(f'starting {self.config} with components {components}')
        return components

    def create_components(self, name: str) -> Either[str, List[Component]]:
        def report(errs):
            msg = 'invalid {} component module "{}": {}'
            self.log.error(msg.format(self.name, name, errs))
        return (
            self.find_component(name)
            .lmap(List)
            .accum_error_f(lambda: self.extra_component(name))
            .leffect(report)
        )

    @property
    def run(self) -> Either[str, List[Component]]:
        comp = self.components()
        sub = comp / self.create_components
        return sub.sequence(Either)


__all__ = ('ComponentResolver',)
