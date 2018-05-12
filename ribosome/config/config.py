from typing import Callable, TypeVar, Generic, Optional, Any

from amino import List, Nil, Map, __, Maybe
from amino.dat import Dat

from ribosome.config.component import Component
from ribosome.compute.program import Program
from ribosome.config.basic_config import NoData, BasicConfig
from ribosome.components.internal.config import internal
from ribosome.rpc.api import RpcProgram

A = TypeVar('A')
D = TypeVar('D')
CC = TypeVar('CC')
G = TypeVar('G')


class Config(Generic[D, CC], Dat['Config[D, CC]']):

    @staticmethod
    def from_opt(data: Map) -> 'Config[D, CC]':
        return Config.cons(data.lift('name') | 'no name in json', data.lift('prefix') | None)

    @staticmethod
    def cons(
            name: str,
            prefix: Optional[str]=None,
            state_ctor: Callable[[], D]=None,
            components: Map[str, Component[Any, CC]]=Map(),
            rpc: List[RpcProgram]=Nil,
            core_components: List[str]=Nil,
            default_components: List[str]=Nil,
            init: Program=None,
            internal_component: bool=True,
    ) -> 'Config[D, CC]':
        basic = BasicConfig.cons(
            name,
            prefix,
            state_ctor,
            core_components,
            default_components,
            internal_component,
        )
        return Config(
            basic,
            components + ('internal', internal) if internal_component else components,
            rpc,
            Maybe.optional(init),
        )

    def __init__(
            self,
            basic: BasicConfig[D],
            components: Map[str, Component[Any, CC]],
            rpc: List[RpcProgram],
            init: Maybe[Program],
    ) -> None:
        self.basic = basic
        self.components = components
        self.rpc = rpc
        self.init = init


__all__ = ('Config', 'NoData')
