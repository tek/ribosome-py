from typing import Callable, Type, TypeVar, Generic, Union, Any, Optional

from amino import List, Nil, Just, Maybe, Map
from amino.dat import Dat

from ribosome.nvim import NvimIO, NvimFacade
from ribosome.data import Data
from ribosome.record import field
from ribosome.request.handler.handler import RequestHandler, RequestHandlers
from ribosome.config.settings import PluginSettings
from ribosome.dispatch.run import DispatchJob

A = TypeVar('A', contravariant=True)
B = TypeVar('B')
Settings = TypeVar('Settings', bound=PluginSettings)
S = TypeVar('S', bound='AutoData')


class Config(Generic[Settings, S], Dat['Config']):

    @staticmethod
    def from_opt(data: Map) -> 'Config':
        return Config(data.lift('name') | 'no name in json', data.lift('prefix') | None)

    def __init__(
            self,
            name: str,
            prefix: Optional[str]=None,
            components: Map[str, Union[str, type]]=Map(),
            state_type: Optional[Type[S]]=None,
            state_ctor: Optional[Callable[['Config', NvimFacade], S]]=None,
            settings: Optional[Settings]=None,
            request_handlers: List[RequestHandler]=Nil,
            core_components: List[str]=Nil,
            default_components: List[str]=Nil,
            request_dispatcher: Optional[Callable[[DispatchJob], NvimIO[Any]]]=None,
    ) -> None:
        self.name = name
        self.prefix = prefix or name
        self.components = components
        self.state_type = state_type or AutoData
        self.state_ctor = state_ctor or (lambda c, v: self.state_type(config=c, vim_facade=Just(v)))
        self.settings = settings or PluginSettings(name=name)
        self.request_handlers = RequestHandlers.cons(*request_handlers)
        self.core_components = core_components
        self.default_components = default_components
        self.request_dispatcher = Maybe.optional(request_dispatcher)

    def _arg_desc(self) -> List[str]:
        return List(str(self.components), str(self.settings), str(self.request_handlers))

    def state(self, vim: NvimFacade) -> S:
        return self.state_ctor(self, vim)

    @property
    def json_repr(self) -> dict:
        return dict(__type__='ribosome.config.Config', name=self.name, prefix=self.prefix)

    def vim_cmd_name(self, handler: RequestHandler) -> str:
        return handler.vim_cmd_name(self.name, self.prefix)


class AutoData(Data):
    config: Config = field(Config)

    @property
    def _str_extra(self) -> List[Any]:
        return List(self.config)

    @property
    def settings(self) -> Settings:
        return self.config.settings


__all__ = ('Config', 'AutoData')
