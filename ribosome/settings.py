import abc
import inspect
from typing import Callable, Type, TypeVar, Generic, Iterable, cast, Union, Any, Optional

from amino import List, Either, Lists, Map, _, L, __, Nil, Path, Right, Try, Nil
from amino.func import flip
from amino.util.string import ToStr

from ribosome.nvim import NvimIO
from ribosome.nvim.components import NvimComponent
from ribosome.logging import Logging
from ribosome.data import Data
from ribosome.machine.message_base import Message
from ribosome.machine.transitions import Transitions
from ribosome.request.command import msg_command, json_msg_command
from ribosome.request.function import msg_function
from ribosome.request.autocmd import msg_autocmd
from ribosome.record import field


A = TypeVar('A', contravariant=True)
B = TypeVar('B')


class PluginSetting(Generic[A, B], ToStr):

    def __init__(
            self,
            name: str,
            desc: str,
            help: str,
            prefix: bool,
            tpe: Type[A],
            ctor: Callable[[A], B],
            default: B,
    ) -> None:
        self.name = name
        self.desc = desc
        self.help = help
        self.prefix = prefix
        self.tpe = tpe
        self.ctor = ctor
        self.default = default

    @property
    def value(self) -> NvimIO[Either[str, A]]:
        def read(v: NvimComponent) -> Either[str, A]:
            vars = v.vars
            getter = vars.p if self.prefix else vars
            return vars.typed(self.tpe, getter(self.name)) // self.ctor
        return NvimIO(read)

    @property
    def value_or_default(self) -> NvimIO[A]:
        return self.value / __.value_or(self.default)

    def value_or(self, default: A) -> NvimIO[A]:
        return self.value / __.value_or(default)

    def _arg_desc(self) -> List[str]:
        return List(self.name, str(self.prefix), str(self.tpe))


def setting_ctor(tpe: Type[A], ctor: Callable[[A], B]) -> Callable[[str, str, str, bool, B], PluginSetting[A, B]]:
    def setting(name: str, desc: str, help: str, prefix: bool, default: B) -> PluginSetting[A, B]:
        return PluginSetting(name, desc, help, prefix, tpe, ctor, default)
    return setting


class PluginSettings(ToStr, Logging):

    def __init__(self) -> None:
        self.components = list_setting('components', 'names or paths of active components', components_help, True, Nil)

    def all(self) -> Map[str, PluginSetting]:
        settings = inspect.getmembers(self, L(isinstance)(_, PluginSetting))
        return Map(Lists.wrap(settings).map(_[1]).apzip(_.name).map2(flip))

    def _arg_desc(self) -> List[str]:
        return List(str(self.all()))


def path_list(data: list) -> Either[str, List[Path]]:
    return Lists.wrap(data).traverse(lambda a: Try(Path, a) / __.expanduser(), Either)


components_help = '''The plugin can run an arbitrary set of sub-components that inherit the class `Component`.
They receive all messages the core of the plugin processes and have access to the plugin state.
They can define nvim request handlers with the decorator `trans.xyz`.
The entries of this setting can either be names of the builtin components or arbitrary python module paths that define
custom plugins.
'''
str_setting = setting_ctor(str, lambda a: Right(a))
list_setting = setting_ctor(list, cast(Callable[[Iterable[A]], Either[str, List[B]]], (lambda a: Right(Lists.wrap(a)))))
path_setting = setting_ctor(str, (lambda a: Try(Path, a)))
path_list_setting = setting_ctor(list, path_list)
map_setting = setting_ctor(dict, lambda a: Right(Map(a)))
path_map_setting = setting_ctor(dict, lambda a: Try(Map, a).valmap(lambda b: Path(b).expanduser()))

M = TypeVar('M', bound=Message)


class RequestDispatcher(ToStr):

    @abc.abstractmethod
    def decorator(self) -> Callable[..., Callable]:
        ...

    @abc.abstractproperty
    def args(self) -> List[Any]:
        ...


class MsgDispatcher(Generic[M], RequestDispatcher):

    def __init__(self, msg: Type[M]) -> None:
        self.msg = msg

    def _arg_desc(self) -> List[str]:
        return List(str(self.msg))

    @property
    def args(self) -> List[Any]:
        return List(self.msg)


class MsgCmd(Generic[M], MsgDispatcher[M]):

    def decorator(self) -> Callable[..., Callable]:
        return msg_command


class JsonMsgCmd(Generic[M], MsgDispatcher[M]):

    def decorator(self) -> Callable[..., Callable]:
        return json_msg_command


class MsgFun(Generic[M], MsgDispatcher[M]):

    def decorator(self) -> Callable[..., Callable]:
        return msg_function


class MsgAutocmd(Generic[M], MsgDispatcher[M]):

    def decorator(self) -> Callable[..., Callable]:
        return msg_autocmd


class PrefixStyle(ToStr):

    def _arg_desc(self) -> List[str]:
        return Nil


class Short(PrefixStyle):
    pass


class Full(PrefixStyle):
    pass


class Plain(PrefixStyle):
    pass


class RequestHandler(ToStr):

    def __init__(self, dispatcher: RequestDispatcher, name: str, prefix: PrefixStyle=Short(), sync: bool=False) -> None:
        self.dispatcher = dispatcher
        self.name = name
        self.prefix = prefix
        self.sync = sync

    @staticmethod
    def msg_cmd(msg: Type[M]) -> 'RequestHandlerBuilder':
        return RequestHandlerBuilder(MsgCmd(msg))

    @staticmethod
    def msg_fun(msg: Type[M]) -> 'RequestHandlerBuilder':
        return RequestHandlerBuilder(MsgFun(msg))

    @staticmethod
    def msg_autocmd(msg: Type[M]) -> 'RequestHandlerBuilder':
        return RequestHandlerBuilder(MsgAutocmd(msg))

    def _arg_desc(self) -> List[str]:
        return List(str(self.dispatcher), self.name, str(self.prefix), str(self.sync))


class RequestHandlerBuilder:

    def __init__(self, dispatcher: RequestDispatcher) -> None:
        self.dispatcher = dispatcher

    def __call__(self, name: str, prefix: PrefixStyle=Short(), sync: bool=False) -> RequestHandler:
        return RequestHandler(self.dispatcher, name, prefix, sync)


class RequestHandlers(ToStr):

    @staticmethod
    def cons(*handlers: RequestHandler) -> 'RequestHandlers':
        return RequestHandlers(Map(Lists.wrap(handlers).apzip(_.name).map2(flip)))

    def __init__(self, handlers: Map[str, RequestHandler]) -> None:
        self.handlers = handlers

    def _arg_desc(self) -> List[str]:
        return List(str(self.handlers))


Settings = TypeVar('Settings', bound=PluginSettings)
S = TypeVar('S', bound='AutoData')
T = TypeVar('T', bound=Transitions)


class Config(Generic[Settings, S], ToStr):

    def __init__(
            self,
            name: str,
            prefix: Optional[str]=None,
            plugins: Map[str, Union[str, Type[T]]]=Map(),
            state_type: Optional[Type[S]]=None,
            settings: Optional[Settings]=None,
            request_handlers: List[RequestHandler]=Nil,
            default_components: List[str]=Nil
    ) -> None:
        self.name = name
        self.prefix = prefix or name
        self.plugins = plugins
        self.state_type = state_type or AutoData
        self.settings = settings or PluginSettings()
        self.request_handlers = RequestHandlers.cons(*request_handlers)
        self.default_components = default_components

    def _arg_desc(self) -> List[str]:
        return List(str(self.plugins), str(self.settings), str(self.request_handlers))


class AutoData(Data):
    config: Config = field(Config)

    @property
    def _str_extra(self) -> List[Any]:
        return List(self.config)

__all__ = ('PluginSetting', 'setting_ctor', 'PluginSettings', 'str_setting', 'list_setting', 'Config',
           'RequestHandlers', 'RequestHandler')
