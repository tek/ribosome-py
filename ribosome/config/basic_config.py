from typing import Callable, TypeVar, Generic

from amino import Dat, List, Nil, Maybe

D = TypeVar('D')


class NoData(Dat['NoData']):
    pass


class BasicConfig(Generic[D], Dat['BasicConfig[D]']):

    @staticmethod
    def cons(
            name: str,
            prefix: str=None,
            state_ctor: Callable[[], D]=None,
            core_components: List[str]=Nil,
            default_components: List[str]=Nil,
            internal_component: bool=True,
            settings_module: str=None,
    ) -> 'BasicConfig':
        return BasicConfig(
            name,
            prefix or name,
            state_ctor or NoData,
            core_components.cons('internal') if internal_component else core_components,
            default_components,
            Maybe.optional(settings_module),
        )

    def __init__(
            self,
            name: str,
            prefix: str,
            state_ctor: Callable,
            core_components: List[str],
            default_components: List[str],
            settings_module: Maybe[str],
    ) -> None:
        self.name = name
        self.prefix = prefix
        self.state_ctor = state_ctor
        self.core_components = core_components
        self.default_components = default_components
        self.settings_module = settings_module


__all__ = ('NoData', 'BasicConfig')
