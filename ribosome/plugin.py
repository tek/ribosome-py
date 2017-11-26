import sys
import typing
from typing import Union, Any, Callable, Type, Optional, TypeVar, Generic, GenericMeta

import neovim
from neovim.api import Nvim

from amino import List

import ribosome.nvim.components
from ribosome.nvim import NvimFacade
from ribosome.logging import nvim_logging, Logging
from ribosome.request.command import command
from ribosome.request.function import function
from ribosome.request.rpc import rpc_handlers_json
from ribosome.record import encode_json_compat, decode_json_compat
# from ribosome.trans.messages import Stage1, Stage2, Stage3, Stage4, Quit
from ribosome.config import Config, PluginSettings
from ribosome.trans.message_base import Message


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

    def send_message(self, data: str) -> None:
        return decode_json_compat(data) / self.root.send


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

#     @abc.abstractmethod
#     def state(self) -> RootMachine:
#         ...

    def message_log(self) -> List[Message]:
        return self.state().message_log // encode_json_compat

    def state_data(self) -> str:
        return self.state().data.json.value_or(lambda a: f'could not serialize state: {a}')

    def plug_command(self, plug_name: str, cmd_name: str, *args: str) -> None:
        self.state().plug_command(plug_name, cmd_name, args)


Settings = TypeVar('Settings', bound=PluginSettings)
D = TypeVar('D')
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
        return super().__new__(cls, name, bases, namespace, pname, prefix, debug)


class AutoPlugin(Generic[Settings, D], NvimStatePlugin, metaclass=AutoPluginMeta):

    def __init__(self, nvim: Union[NvimFacade, neovim.Nvim], config: Config[Settings, D], initial_state: D) -> None:
        super().__init__(nvim)
        self.config = config
        self.initial_state = initial_state
        # self.root = self.create_root()

    # def create_root(self) -> RootMachine[Settings, D]:
    #     return root_machine(self.vim.proxy, self.config, self.initial_state)

#     def stage_1(self) -> None:
#         self.root.start()
#         self.root.wait_for_running()
#         self.root.send(Stage1())

#     def stage_2(self) -> None:
#         self.root.send(Stage2().at(0.6))

#     def stage_3(self) -> None:
#         self.root.send(Stage3().at(0.7))

#     def stage_4(self) -> None:
#         self.root.send(Stage4().at(0.8))

    # def quit(self) -> None:
    #     self.root.send(Quit())

    # def state(self) -> RootMachine:
    #     return self.root


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

    # def msg_cmd(self, suf: str, msg: type) -> None:
    #     self.short_handler(suf, msg_command, lambda: None, msg)

    # def msg_fun(self, suf: str, msg: type) -> None:
    #     self.short_handler(suf, msg_function, lambda: None, msg)

    # def json_msg_cmd(self, suf: str, msg: type) -> None:
    #     self.short_handler(suf, json_msg_command, lambda: None, msg)


def setup_plugin(cls: Type[NvimPlugin], name: str, prefix: str, debug: bool) -> None:
    help = Helpers(cls, name, prefix)
    cls.name = name
    cls.prefix = prefix
    cls.debug = debug
    # help.msg_cmd('show_log_info', ShowLogInfo)
    help.short_handler('log_level', command, cls.set_log_level)
    # help.msg_fun('mapping', Mapping)
    # help.name_handler('stage_1', command, cls.stage_1, sync=True)
    # help.name_handler('stage_2', command, cls.stage_2, sync=True)
    # help.name_handler('stage_3', command, cls.stage_3, sync=True)
    # help.name_handler('stage_4', command, cls.stage_4, sync=True)
    # help.name_handler('quit', command, cls.quit, sync=True)
    help.name_handler('rpc_handlers', function, cls.rpc_handlers, sync=True)
    help.name_handler('append_python_path', function, cls.append_python_path)
    help.name_handler('show_python_path', function, cls.show_python_path)
    help.name_handler('send', function, cls.send_message)


def setup_state_plugin(cls: Type[NSP], name: str, prefix: str, debug: bool) -> None:
    help = Helpers(cls, name, prefix)
    help.short_handler('state', function, cls.state_data)
    # help.json_msg_cmd('update_state', UpdateState)
    help.short_handler('plug', command, cls.plug_command)
    # if debug:
    #     help.name_handler('message_log', function, cls.message_log, sync=True)


def plugin_class_from_config(config: Config[Settings, D], cls: Type[AP], debug=bool) -> Type[AP]:
    class Plug(AutoPlugin, config=config, pname=config.name, prefix=config.prefix, debug=debug):
        def __init__(self, vim: Nvim, initial_state: D) -> None:
            super().__init__(vim, config, initial_state)
    return type(cls.__name__, (cls, Plug), {})

__all__ = ('NvimPlugin', 'NvimStatePlugin')
