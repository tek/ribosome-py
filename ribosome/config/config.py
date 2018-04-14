from typing import Callable, TypeVar, Generic, Optional, Type, Any

from amino import List, Nil, Map, Either, Right, do, Do, Maybe
from amino.dat import Dat
from amino.json.encoder import Encoder, json_object_with_type
from amino.json.data import JsonError, Json, JsonScalar
from amino.json.decoder import Decoder, decode

from ribosome.request.handler.handler import RequestHandler, RequestHandlers
from ribosome.config.settings import Settings
from ribosome.request.rpc import RpcHandlerSpec
from ribosome.config.component import Component
from ribosome.compute.program import Program
from ribosome.config.basic_config import NoData, BasicConfig
from ribosome.components.internal.config import internal

A = TypeVar('A')
D = TypeVar('D')
S = TypeVar('S', bound=Settings)
CC = TypeVar('CC')
G = TypeVar('G')


class Config(Generic[S, D, CC], Dat['Config[S, D, CC]']):

    @staticmethod
    def from_opt(data: Map) -> 'Config[S, D, CC]':
        return Config.cons(data.lift('name') | 'no name in json', data.lift('prefix') | None)

    @staticmethod
    def cons(
            name: str,
            prefix: Optional[str]=None,
            state_ctor: Callable[[], D]=None,
            components: Map[str, Component[D, Any, CC]]=Map(),
            settings: S=None,
            request_handlers: List[RequestHandler]=Nil,
            core_components: List[str]=Nil,
            default_components: List[str]=Nil,
            init: Program=None,
            internal_component: bool=True,
    ) -> 'Config[S, D, CC]':
        basic = BasicConfig.cons(
            name,
            prefix,
            state_ctor,
            settings,
            core_components,
            default_components,
            internal_component,
        )
        return Config(
            basic,
            components + ('internal', internal) if internal_component else components,
            RequestHandlers.cons(*request_handlers),
            Maybe.optional(init),
        )

    def __init__(
            self,
            basic: BasicConfig[S, D],
            components: Map[str, Component[D, Any, CC]],
            request_handlers: RequestHandlers,
            init: Maybe[Program],
    ) -> None:
        self.basic = basic
        self.components = components
        self.request_handlers = request_handlers
        self.init = init

    def _arg_desc(self) -> List[str]:
        return List(str(self.components), str(self.settings), str(self.request_handlers))

    def vim_cmd_name(self, handler: RequestHandler) -> str:
        return handler.vim_cmd_name(self.name, self.prefix)

    @property
    def rpc_specs(self) -> List[RpcHandlerSpec]:
        return self.request_handlers.rpc_specs(self.name, self.prefix)


class ConfigEncoder(Encoder[Config], tpe=Config):

    def encode(self, a: Config) -> Either[JsonError, Map]:
        return Right(json_object_with_type(Map(name=JsonScalar(a.name)), Config))


class ConfigDecoder(Decoder[Config], tpe=Config):

    @do(Either[JsonError, Config])
    def decode(self, tpe: Type[Config], data: Json) -> Do:
        f = yield data.field('name')
        name = yield decode(f)
        yield Right(Config.cons(name))


__all__ = ('Config', 'NoData', 'Resources')
