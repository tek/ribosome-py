from typing import Callable, TypeVar, Generic, Union, Optional, Type

from amino import List, Nil, Map, Either, Right, do, Do
from amino.dat import Dat
from amino.json.encoder import Encoder, json_object_with_type
from amino.json.data import JsonError, Json, JsonScalar
from amino.json.decoder import Decoder, decode

from ribosome.request.handler.handler import RequestHandler, RequestHandlers
from ribosome.config.settings import Settings
from ribosome.request.rpc import RpcHandlerSpec

A = TypeVar('A', contravariant=True)
B = TypeVar('B')
D = TypeVar('D')
S = TypeVar('S', bound=Settings)


class SimpleData(Dat['SimpleData']):
    pass


class Config(Generic[S, D], Dat['Config[S, D]']):

    @staticmethod
    def from_opt(data: Map) -> 'Config[S, D]':
        return Config.cons(data.lift('name') | 'no name in json', data.lift('prefix') | None)

    @staticmethod
    def cons(
            name: str,
            prefix: Optional[str]=None,
            components: Map[str, Union[str, type]]=Map(),
            state_ctor: Optional[Callable[['Config'], D]]=None,
            settings: Optional[S]=None,
            request_handlers: List[RequestHandler]=Nil,
            core_components: List[str]=Nil,
            default_components: List[str]=Nil,
    ) -> 'Config[S, D]':
        from ribosome.trans.internal import internal
        return Config(
            name,
            prefix or name,
            components + ('internal', internal),
            state_ctor or SimpleData,
            settings or Settings(name=name),
            RequestHandlers.cons(*request_handlers),
            core_components.cons('internal'),
            default_components,
        )

    def __init__(
            self,
            name: str,
            prefix: str,
            components: Map[str, Union[str, type]],
            state_ctor: Callable[['Config'], D],
            settings: S,
            request_handlers: RequestHandlers,
            core_components: List[str],
            default_components: List[str],
    ) -> None:
        self.name = name
        self.prefix = prefix
        self.components = components
        self.state_ctor = state_ctor
        self.settings = settings
        self.request_handlers = request_handlers
        self.core_components = core_components
        self.default_components = default_components

    def _arg_desc(self) -> List[str]:
        return List(str(self.components), str(self.settings), str(self.request_handlers))

    def state(self) -> D:
        return self.state_ctor()

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


class Resources(Generic[S, D], Dat['Resources[S, D]']):

    def __init__(self, settings: S, data: D) -> None:
        self.settings = settings
        self.data = data


__all__ = ('Config', 'SimpleData', 'Resources')
