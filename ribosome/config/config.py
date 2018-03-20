from typing import Callable, TypeVar, Generic, Union, Optional, Type, Any

from amino import List, Nil, Map, Either, Right, do, Do, Maybe
from amino.dat import Dat
from amino.json.encoder import Encoder, json_object_with_type
from amino.json.data import JsonError, Json, JsonScalar
from amino.json.decoder import Decoder, decode
from amino.state import StateT

from ribosome.request.handler.handler import RequestHandler, RequestHandlers
from ribosome.config.settings import Settings
from ribosome.request.rpc import RpcHandlerSpec
from ribosome.dispatch.component import Components
from ribosome.trans.handler import TransF

A = TypeVar('A')
D = TypeVar('D')
S = TypeVar('S', bound=Settings)
CC = TypeVar('CC')
G = TypeVar('G')


class NoData(Dat['NoData']):
    pass


class Config(Generic[S, D, CC], Dat['Config[S, D, CC]']):

    @staticmethod
    def from_opt(data: Map) -> 'Config[S, D, CC]':
        return Config.cons(data.lift('name') | 'no name in json', data.lift('prefix') | None)

    @staticmethod
    def cons(
            name: str,
            prefix: Optional[str]=None,
            components: Map[str, Union[str, type]]=Map(),
            state_ctor: Optional[Callable[[], D]]=None,
            settings: Optional[S]=None,
            request_handlers: List[RequestHandler]=Nil,
            core_components: List[str]=Nil,
            default_components: List[str]=Nil,
            component_config_type: Type[CC]=Any,
            init: TransF=None,
    ) -> 'Config[S, D, CC]':
        from ribosome.trans.internal import internal
        return Config(
            name,
            prefix or name,
            components + ('internal', internal),
            state_ctor or NoData,
            settings or Settings(name=name),
            RequestHandlers.cons(*request_handlers),
            core_components.cons('internal'),
            default_components,
            component_config_type,
            Maybe.optional(init),
        )

    def __init__(
            self,
            name: str,
            prefix: str,
            components: Map[str, Union[str, type]],
            state_ctor: Callable[[], D],
            settings: S,
            request_handlers: RequestHandlers,
            core_components: List[str],
            default_components: List[str],
            component_config_type: Type[CC],
            init: Maybe[TransF],
    ) -> None:
        self.name = name
        self.prefix = prefix
        self.components = components
        self.state_ctor = state_ctor
        self.settings = settings
        self.request_handlers = request_handlers
        self.core_components = core_components
        self.default_components = default_components
        self.component_config_type = component_config_type
        self.init = init

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


class Resources(Generic[S, D, CC], Dat['Resources[S, D, CC]']):

    def __init__(self, data: D, settings: S, components: Components[D, CC]) -> None:
        self.data = data
        self.settings = settings
        self.components = components


def resources_lift(st: StateT[G, D, A]) -> StateT[G, Resources[S, D, CC], A]:
    def trans(r: Resources[S, D, CC]) -> G:
        return st.run(r.data).map2(lambda s, a: (Resources(s, r.settings, r.components), a))
    return st.cls.apply(trans)

__all__ = ('Config', 'NoData', 'Resources')
