from typing import Callable, TypeVar, Generic, Optional, Type, Any

from amino import List, Nil, Map, Either, Right, do, Do, Maybe, __
from amino.dat import Dat
from amino.json.encoder import Encoder, json_object_with_type
from amino.json.data import JsonError, Json, JsonScalar
from amino.json.decoder import Decoder, decode

from ribosome.request.handler.handler import RequestHandler, RequestHandlers, RpcProgram
from ribosome.request.rpc import RpcHandlerSpec
from ribosome.config.component import Component
from ribosome.compute.program import Program
from ribosome.config.basic_config import NoData, BasicConfig
from ribosome.components.internal.config import internal

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
            components: Map[str, Component[D, Any, CC]]=Map(),
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
            components: Map[str, Component[D, Any, CC]],
            rpc: List[RpcProgram],
            init: Maybe[Program],
    ) -> None:
        self.basic = basic
        self.components = components
        self.rpc = rpc
        self.init = init

    def vim_cmd_name(self, handler: RequestHandler) -> str:
        return handler.vim_cmd_name(self.name, self.prefix)

    @property
    def rpc_specs(self) -> List[RpcHandlerSpec]:
        return self.rpc / __.spec(self.name, self.prefix)


__all__ = ('Config', 'NoData')
