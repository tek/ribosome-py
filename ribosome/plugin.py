import abc
from typing import Union, Any, Callable

import neovim

from ribosome.nvim import NvimFacade
from ribosome.machine import StateMachine
from ribosome.logging import nvim_logging, Logging
from ribosome.request import msg_command, msg_function, command
from ribosome.machine.base import ShowLogInfo
from ribosome.machine.scratch import Mapping


class NvimPlugin(Logging):
    name: str = None
    prefix: str = None

    def __init_subclass__(cls: type, name: str=None, prefix: str=None) -> None:
        if name is not None:
            setup_plugin(cls, name, prefix or name)

    def __init__(self, nvim: Union[NvimFacade, neovim.Nvim]) -> None:
        self.vim = NvimFacade(nvim, self.name) if isinstance(nvim, neovim.Nvim) else nvim
        self.setup_logging()

    def setup_logging(self) -> None:
        self.file_log_handler = nvim_logging(self.vim)

    @property
    def loop(self) -> Any:
        return self.vim.loop

    @property
    def name(self) -> str:
        return 'ribosome'

    @abc.abstractmethod
    def start_plugin(self) -> None:
        ...

    def set_log_level(self, level: str) -> None:
        self.file_log_handler.setLevel(level)


class NvimStatePlugin(NvimPlugin):

    @abc.abstractproperty
    def state(self) -> StateMachine:
        ...

    @property
    def default_sync(self) -> bool:
        return False


def setup_plugin(cls: type, name: str, prefix: str) -> None:
    def name_handler(suf: str, handler: Callable[..., None]) -> None:
        setattr(cls, f'{name}_{suf}', handler)
    def handler(suf: str, handler: Callable[..., None]) -> None:
        setattr(cls, f'{prefix}_{suf}', handler)
    def msg_cmd(suf: str, msg: type) -> None:
        handler(suf, msg_command(msg)(lambda: None))
    def msg_fun(suf: str, msg: type) -> None:
        handler(suf, msg_function(msg)(lambda: None))
    cls.name = name
    cls.prefix = prefix
    msg_cmd('show_log_info', ShowLogInfo)
    handler('log_level', NvimPlugin.set_log_level)
    msg_fun('mapping', Mapping)
    name_handler('start', command(sync=True)(NvimPlugin.start_plugin))

__all__ = ('NvimPlugin', 'NvimStatePlugin')
