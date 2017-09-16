import abc
import inspect
from typing import Callable, Type, TypeVar, Generic, Iterable, cast, Union, Any
from enum import Enum

from amino import List, Either, Lists, Map, _, L, __, Nil
from amino.func import flip
from amino.util.string import ToStr

from ribosome.nvim import NvimIO
from ribosome.nvim.components import NvimComponent
from ribosome.logging import Logging
from ribosome.data import Data
from ribosome.machine.message_base import Message
from ribosome.machine.transitions import Transitions
from ribosome.request import command, function, msg_command, json_msg_command, msg_function


A = TypeVar('A', contravariant=True)
B = TypeVar('B')


class PluginSetting(Generic[A, B], ToStr):

    def __init__(self, name: str, desc: str, help: str, prefix: bool, tpe: Type[A], ctor: Callable[[A], B]) -> None:
        self.name = name
        self.desc = desc
        self.help = help
        self.prefix = prefix
        self.tpe = tpe
        self.ctor = ctor

    @property
    def value(self) -> NvimIO[Either[str, A]]:
        def read(v: NvimComponent) -> Either[str, A]:
            vars = v.vars
            getter = vars.p if self.prefix else vars
            return vars.typed(self.tpe, getter(self.name))
        return NvimIO(read)

    def value_or(self, default: A) -> NvimIO[A]:
        return self.value / __.value_or(default)

    def _arg_desc(self) -> List[str]:
        return List(self.name, str(self.prefix), str(self.tpe))


def setting_ctor(tpe: Type[A], ctor: Callable[[A], B]) -> Callable[[str, str, str, bool], PluginSetting[A, B]]:
    def setting(name: str, desc: str, help: str, prefix: bool) -> PluginSetting[A, B]:
        return PluginSetting(name, desc, help, prefix, tpe, ctor)
    return setting


class PluginSettings(ToStr, Logging):

    def __init__(self) -> None:
        self.components = list_setting('components', 'names or paths of active components', components_help, True)

    def all(self) -> Map[str, PluginSetting]:
        settings = inspect.getmembers(self, L(isinstance)(_, PluginSetting))
        return Map(Lists.wrap(settings).map(_[1]).apzip(_.name).map2(flip))

    def _arg_desc(self) -> List[str]:
        return List(str(self.all()))


components_help = '''The plugin can run an arbitrary set of sub-components that inherit the class `Component`.
They receive all messages the core of the plugin processes and have access to the plugin state.
They can define nvim request handlers with the decorator `trans.xyz`.
The entries of this setting can either be names of the builtin components or arbitrary python module paths that define
custom plugins.
'''
str_setting = setting_ctor(str, lambda a: a)
list_setting = setting_ctor(list, cast(Callable[[Iterable[A]], List[B]], Lists.wrap))

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

    def __init__(self, dispatcher: RequestDispatcher, name: str, prefix: PrefixStyle=Short, sync: bool=False) -> None:
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

    def _arg_desc(self) -> List[str]:
        return List(str(self.dispatcher), self.name, str(self.prefix), str(self.sync))


class RequestHandlerBuilder:

    def __init__(self, dispatcher: RequestDispatcher) -> None:
        self.dispatcher = dispatcher

    def __call__(self, name: str, prefix: bool=True, sync: bool=False) -> RequestHandler:
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
S = TypeVar('S', bound=Data)
T = TypeVar('T', bound=Transitions)


class Config(Generic[Settings, S], ToStr):

    def __init__(self, name: str, prefix: str, plugins: Map[str, Union[str, Type[T]]], state_type: Type[S],
                 settings: Settings, request_handlers: RequestHandlers) -> None:
        self.name = name
        self.prefix = prefix
        self.plugins = plugins
        self.state_type = state_type
        self.settings = settings
        self.request_handlers = request_handlers

    def _arg_desc(self) -> List[str]:
        return List(str(self.plugins), str(self.settings), str(self.request_handlers))

__all__ = ('PluginSetting', 'setting_ctor', 'PluginSettings', 'str_setting', 'list_setting', 'Config',
           'RequestHandlers', 'RequestHandler')
