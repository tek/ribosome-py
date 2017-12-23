from typing import Callable, TypeVar, Generic, Union, Any, Optional, Type

from amino import List, Nil, Maybe, Map, Either, Right, do, Do
from amino.dat import Dat
from amino.json.encoder import Encoder, json_object_with_type
from amino.json.data import JsonError, Json, JsonScalar
from amino.json.decoder import Decoder, decode

from ribosome.nvim import NvimIO
from ribosome.request.handler.handler import RequestHandler, RequestHandlers
from ribosome.config.settings import PluginSettings
from ribosome.dispatch.run import DispatchJob
from ribosome.request.rpc import RpcHandlerSpec

A = TypeVar('A', contravariant=True)
B = TypeVar('B')
Settings = TypeVar('Settings', bound=PluginSettings)
D = TypeVar('D', bound='SimpleData')


class Config(Generic[Settings, D], Dat['Config[Settings, D]']):

    @staticmethod
    def from_opt(data: Map) -> 'Config[Settings, D]':
        return Config.cons(data.lift('name') | 'no name in json', data.lift('prefix') | None)

    @staticmethod
    def cons(
            name: str,
            prefix: Optional[str]=None,
            components: Map[str, Union[str, type]]=Map(),
            state_ctor: Optional[Callable[['Config'], D]]=None,
            settings: Optional[Settings]=None,
            request_handlers: List[RequestHandler]=Nil,
            core_components: List[str]=Nil,
            default_components: List[str]=Nil,
            request_dispatcher: Optional[Callable[[DispatchJob], NvimIO[Any]]]=None,
    ) -> 'Config[Settings, D]':
        return Config(
            name,
            prefix or name,
            components,
            state_ctor or SimpleData,
            settings or PluginSettings(name=name),
            RequestHandlers.cons(*request_handlers),
            core_components,
            default_components,
            Maybe.optional(request_dispatcher),
        )

    def __init__(
            self,
            name: str,
            prefix: str,
            components: Map[str, Union[str, type]],
            state_ctor: Callable[['Config'], D],
            settings: Settings,
            request_handlers: RequestHandlers,
            core_components: List[str],
            default_components: List[str],
            request_dispatcher: Maybe[Callable[[DispatchJob], NvimIO[Any]]],
    ) -> None:
        self.name = name
        self.prefix = prefix
        self.components = components
        self.state_ctor = state_ctor
        self.settings = settings
        self.request_handlers = request_handlers
        self.core_components = core_components
        self.default_components = default_components
        self.request_dispatcher = request_dispatcher

    def _arg_desc(self) -> List[str]:
        return List(str(self.components), str(self.settings), str(self.request_handlers))

    def state(self) -> D:
        return self.state_ctor(self)

    def vim_cmd_name(self, handler: RequestHandler) -> str:
        return handler.vim_cmd_name(self.name, self.prefix)

    @property
    def rpc_specs(self) -> List[RpcHandlerSpec]:
        return self.request_handlers.rpc_specs(self.name, self.prefix)


class Data:

    def __init__(self, config: Config) -> None:
        self.config = config

    @property
    def _str_extra(self) -> List[Any]:
        return List(self.config)

    @property
    def settings(self) -> Settings:
        return self.config.settings


class SimpleData(Dat['SimpleData'], Data):

    def __init__(self, config: Config) -> None:
        super().__init__(config)


class ConfigEncoder(Encoder[Config], tpe=Config):

    def encode(self, a: Config) -> Either[JsonError, Map]:
        return Right(json_object_with_type(Map(name=JsonScalar(a.name)), Config))


class ConfigDecoder(Decoder[Config], tpe=Config):

    @do(Either[JsonError, Config])
    def decode(self, tpe: Type[Config], data: Json) -> Do:
        f = yield data.field('name')
        name = yield decode(f)
        yield Right(Config.cons(name))


__all__ = ('Config', 'Data', 'SimpleData')
