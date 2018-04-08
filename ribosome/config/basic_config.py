from typing import Callable, TypeVar, Generic

from amino import Dat, List, Nil

from ribosome.config.settings import Settings

D = TypeVar('D')
S = TypeVar('S', bound=Settings)


class NoData(Dat['NoData']):
    pass


class BasicConfig(Generic[S, D], Dat['BasicConfig[D]']):

    @staticmethod
    def cons(
            name: str,
            prefix: str=None,
            state_ctor: Callable[[], D]=None,
            settings: S=None,
            core_components: List[str]=Nil,
            default_components: List[str]=Nil,
            internal_component: bool=True,
    ) -> 'BasicConfig':
        return BasicConfig(
            name,
            prefix or name,
            state_ctor or NoData,
            settings or Settings(name=name),
            core_components.cons('internal') if internal_component else core_components,
            default_components,
        )

    def __init__(
            self,
            name: str,
            prefix: str,
            state_ctor: Callable,
            settings: S,
            core_components: List[str],
            default_components: List[str],
    ) -> None:
        self.name = name
        self.prefix = prefix
        self.state_ctor = state_ctor
        self.settings = settings
        self.core_components = core_components
        self.default_components = default_components


__all__ = ('NoData', 'BasicConfig')
