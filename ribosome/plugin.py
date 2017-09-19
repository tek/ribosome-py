import sys
import abc
import typing
from typing import Union, Any, Callable, Type, Optional, TypeVar, Generic, GenericMeta

import neovim

from amino import List

import ribosome.nvim.components
from ribosome.nvim import NvimFacade
from ribosome.machine.message_base import Message
from ribosome.logging import nvim_logging, Logging
from ribosome.request.command import msg_command, command, json_msg_command
from ribosome.request.function import msg_function, function
from ribosome.machine.base import ShowLogInfo
from ribosome.machine.scratch import Mapping
from ribosome.rpc import rpc_handlers_json
from ribosome.record import encode_json
from ribosome.machine.messages import UpdateState, Stage1
from ribosome.machine.state import AutoRootMachine, AutoData, RootMachineBase
from ribosome.settings import Config, PluginSettings, Full, Short


class NvimPluginBase(Logging):
    name: Optional[str] = None
    debug: bool = False

    @property
    def plugin_name(self) -> str:
        return type(self).name or 'ribosome'

    def __init__(self, nvim: Union[NvimFacade, neovim.Nvim]) -> None:
        self.vim = NvimFacade(nvim, self.plugin_name) if isinstance(nvim, neovim.Nvim) else nvim
        self.setup_logging()

    def setup_logging(self) -> None:
        self.file_log_handler = nvim_logging(self.vim)


NB = TypeVar('NB', bound=NvimPluginBase)
N = TypeVar('N', bound='NvimPlugin')
NM = TypeVar('NM', bound='NvimPluginMeta')


class NvimPluginMeta(GenericMeta):

    def __new__(
            cls: Type[NM],
            name: str,
            bases: tuple,
            namespace: dict,
            pname: str=None,
            prefix: str=None,
            debug: bool=False
    ) -> Type[N]:
        inst: Type[N] = super().__new__(cls, name, bases, namespace)
        if pname is not None:
            setup_plugin(inst, pname, prefix or pname, debug)
        return inst


class NvimPlugin(NvimPluginBase, metaclass=NvimPluginMeta):
    prefix: Optional[str] = None

    def stage_1(self) -> None:
        pass

    def stage_2(self) -> None:
        pass

    def stage_3(self) -> None:
        pass

    def stage_4(self) -> None:
        pass

    def quit(self) -> None:
        pass

    def rpc_handlers(self) -> List[str]:
        return rpc_handlers_json(type(self))

    def set_log_level(self, level: str) -> None:
        self.file_log_handler.setLevel(level)

    def append_python_path(self, path: str) -> None:
        sys.path.append(path)

    def show_python_path(self) -> typing.List[str]:
        return sys.path

    @neovim.autocmd('VimLeave', sync=True)
    def vim_leave(self) -> None:
        ribosome.nvim.components.shutdown = True
        self.quit()


NSP = TypeVar('NSP', bound='NvimStatePlugin')
NSPM = TypeVar('NSPM', bound='NvimStatePluginMeta')


class NvimStatePluginMeta(NvimPluginMeta):

    def __new__(
            cls: Type[NSPM],
            name: str,
            bases: tuple,
            namespace: dict,
            pname: str=None,
            prefix: str=None,
            debug: bool=False
    ) -> Type[NSP]:
        inst: Type[NSP] = super().__new__(cls, name, bases, namespace, pname, prefix, debug)
        if inst.name is not None:
            setup_state_plugin(inst, inst.name, inst.prefix or inst.name, debug)
        return inst


class NvimStatePlugin(NvimPlugin, metaclass=NvimStatePluginMeta):

    @abc.abstractmethod
    def state(self) -> RootMachineBase:
        ...

    def message_log(self) -> List[Message]:
        return self.state().message_log // encode_json

    def state_data(self) -> str:
        return self.state().data.json | '{}'

    def plug_command(self, plug_name: str, cmd_name: str, *args: str) -> None:
        self.state().plug_command(plug_name, cmd_name, args)


Settings = TypeVar('Settings', bound=PluginSettings)
D = TypeVar('D', bound=AutoData)
APM = TypeVar('APM', bound='AutoPluginMeta')
AP = TypeVar('AP', bound='AutoPlugin')


class AutoPluginMeta(NvimStatePluginMeta):

    def __new__(
            cls: Type[APM],
            name: str,
            bases: tuple,
            namespace: dict,
            pname: str=None,
            prefix: str=None,
            debug: bool=False,
            config: Config[Settings, D]=None,
    ) -> Type['AutoPlugin[Settings, D]']:
        inst: Type[AutoPlugin[Settings, D]] = super().__new__(cls, name, bases, namespace, pname, prefix, debug)
        if config is not None:
            setup_auto_plugin(inst, config)
        return inst


class AutoPlugin(Generic[Settings, D], NvimStatePlugin, metaclass=AutoPluginMeta):

    def __init__(self, nvim: Union[NvimFacade, neovim.Nvim], config: Config[Settings, D]) -> None:
        super().__init__(nvim)
        self.config = config
        self.root = self.create_root()

    def create_root(self) -> AutoRootMachine[Settings, D]:
        title = self.plugin_name
        return AutoRootMachine(self.vim.proxy, self.config, title)

    def stage_1(self) -> None:
        self.root.start()
        self.root.wait_for_running()
        self.root.send(Stage1())

    def state(self) -> RootMachineBase:
        return self.root


class Helpers(Logging):

    def __init__(self, cls: type, name: str, prefix: str) -> None:
        self.cls = cls
        self.name = name
        self.prefix = prefix

    def handler(self, name: str, dec: Callable[..., Callable], handler: Callable, *a: Any, **kw: Any) -> None:
        def wrap(self: Any, *a: Any, **kw: Any) -> Any:
            try:
                return handler(self, *a, **kw)
            except Exception as e:
                self.log.caught_exception_error(f'calling handler `{name}`', e)
        func = dec(*a, name=name, **kw)(wrap)
        setattr(self.cls, name, func)

    def name_handler(self, suf: str, dec: Callable[..., Callable], handler: Callable, *a: Any, **kw: Any) -> None:
        n = f'{self.name}_{suf}'
        self.handler(n, dec, handler, *a, **kw)

    def short_handler(self, suf: str, dec: Callable[..., Callable], handler: Callable, *a: Any, **kw: Any) -> None:
        n = f'{self.prefix}_{suf}'
        self.handler(n, dec, handler, *a, **kw)

    def msg_cmd(self, suf: str, msg: type) -> None:
        self.short_handler(suf, msg_command, lambda: None, msg)

    def msg_fun(self, suf: str, msg: type) -> None:
        self.short_handler(suf, msg_function, lambda: None, msg)

    def json_msg_cmd(self, suf: str, msg: type) -> None:
        self.short_handler(suf, json_msg_command, lambda: None, msg)


def setup_plugin(cls: Type[NvimPlugin], name: str, prefix: str, debug: bool) -> None:
    help = Helpers(cls, name, prefix)
    cls.name = name
    cls.prefix = prefix
    cls.debug = debug
    help.msg_cmd('show_log_info', ShowLogInfo)
    help.short_handler('log_level', command, cls.set_log_level)
    help.msg_fun('mapping', Mapping)
    help.name_handler('stage_1', command, cls.stage_1, sync=True)
    help.name_handler('stage_2', command, cls.stage_2, sync=True)
    help.name_handler('stage_3', command, cls.stage_3, sync=True)
    help.name_handler('stage_4', command, cls.stage_4, sync=True)
    help.name_handler('quit', command, cls.quit, sync=True)
    help.name_handler('rpc_handlers', function, cls.rpc_handlers, sync=True)
    help.name_handler('append_python_path', function, cls.append_python_path)
    help.name_handler('show_python_path', function, cls.show_python_path)


def setup_state_plugin(cls: Type[NSP], name: str, prefix: str, debug: bool) -> None:
    help = Helpers(cls, name, prefix)
    help.short_handler('state', function, cls.state_data)
    help.json_msg_cmd('update_state', UpdateState)
    help.short_handler('plug', command, cls.plug_command)
    if debug:
        help.name_handler('message_log', function, cls.message_log, sync=True)


def setup_auto_plugin(cls: Type[AutoPlugin], config: Config[Settings, D]) -> None:
    help = Helpers(cls, config.name, config.prefix)
    for hname, handler in config.request_handlers.handlers.items():
        dispatcher = handler.dispatcher
        helper = (
            help.short_handler
            if handler.prefix is Short else
            help.name_handler
            if handler.prefix is Full else
            help.handler
        )
        helper(handler.name, dispatcher.decorator(), lambda: None, *dispatcher.args)

__all__ = ('NvimPlugin', 'NvimStatePlugin')
