import abc
from typing import Union, Any, Callable, Type

import neovim

from amino import List, _

from ribosome.nvim import NvimFacade
from ribosome.machine import StateMachine, Message
from ribosome.logging import nvim_logging, Logging
from ribosome.request import msg_command, msg_function, command, function
from ribosome.machine.base import ShowLogInfo
from ribosome.machine.scratch import Mapping
from ribosome.rpc import rpc_handlers
from ribosome.record import encode_json


class NvimPlugin(Logging):
    name: str = None
    prefix: str = None

    def __init_subclass__(cls: type, name: str=None, prefix: str=None, debug=False) -> None:
        if name is not None:
            setup_plugin(cls, name, prefix or name, debug)

    def __init__(self, nvim: Union[NvimFacade, neovim.Nvim]) -> None:
        self.vim = NvimFacade(nvim, self.plugin_name) if isinstance(nvim, neovim.Nvim) else nvim
        self.setup_logging()

    def setup_logging(self) -> None:
        self.file_log_handler = nvim_logging(self.vim)

    @property
    def loop(self) -> Any:
        return self.vim.loop

    @property
    def plugin_name(self) -> str:
        return type(self).name or 'ribosome'

    @abc.abstractmethod
    def start_plugin(self) -> None:
        ...

    def rpc_handlers(self) -> List[dict]:
        return list(rpc_handlers(type(self)) / _.encode)

    def set_log_level(self, level: str) -> None:
        self.file_log_handler.setLevel(level)


class NvimStatePlugin(NvimPlugin):

    def __init_subclass__(cls: type, name: str=None, prefix: str=None, debug=False) -> None:
        super().__init_subclass__(name, prefix, debug)
        if debug and cls.name:
            setup_debug_state_plugin(cls, cls.name, cls.prefix)

    @abc.abstractmethod
    def state(self) -> StateMachine:
        ...

    def message_log(self) -> List[Message]:
        return self.state().message_log // encode_json


UnitF = Callable[..., None]


class Helpers:

    def __init__(self, cls: type, name: str, prefix: str) -> None:
        self.cls = cls
        self.name = name
        self.prefix = prefix

    def _handler(self, name: str, dec: Callable[..., UnitF], handler: UnitF, *a: Any, **kw: Any) -> None:
        func = dec(*a, name=name, **kw)(handler)
        setattr(self.cls, name, func)

    def name_handler(self, suf: str, dec: Callable[..., UnitF], handler: UnitF, *a: Any, **kw: Any) -> None:
        n = f'{self.name}_{suf}'
        self._handler(n, dec, handler, *a, **kw)

    def handler(self, suf: str, dec: Callable[..., UnitF], handler: UnitF, *a: Any, **kw: Any) -> None:
        n = f'{self.prefix}_{suf}'
        self._handler(n, dec, handler, *a, **kw)

    def msg_cmd(self, suf: str, msg: type) -> None:
        self.handler(suf, msg_command, lambda: None, msg)

    def msg_fun(self, suf: str, msg: type) -> None:
        self.handler(suf, msg_function, lambda: None, msg)


def setup_plugin(cls: Type[NvimPlugin], name: str, prefix: str, debug: bool) -> None:
    help = Helpers(cls, name, prefix)
    cls.name = name
    cls.prefix = prefix
    cls.debug = debug
    help.msg_cmd('show_log_info', ShowLogInfo)
    help.handler('log_level', command, cls.set_log_level)
    help.msg_fun('mapping', Mapping)
    help.name_handler('start', command, cls.start_plugin, sync=True)
    help.name_handler('rpc_handlers', function, cls.rpc_handlers, sync=True)


def setup_debug_state_plugin(cls: Type[NvimStatePlugin], name: str, prefix: str) -> None:
    help = Helpers(cls, name, prefix)
    help.name_handler('message_log', function, cls.message_log, sync=True)

__all__ = ('NvimPlugin', 'NvimStatePlugin')
