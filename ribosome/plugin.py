import abc
from typing import Union, Any

import neovim

from ribosome.nvim import NvimFacade
from ribosome.machine import StateMachine
from ribosome.logging import nvim_logging, Logging


class NvimPlugin(Logging):

    def __init__(self, nvim: Union[NvimFacade, neovim.Nvim]) -> None:
        if isinstance(nvim, neovim.Nvim):
            nvim = NvimFacade(nvim, self.name)
        self.vim = nvim
        self.setup_logging()

    def setup_logging(self) -> None:
        nvim_logging(self.vim)

    @property
    def loop(self) -> Any:
        return self.vim.loop

    @property
    def name(self) -> str:
        return 'ribosome'

    def start_plugin(self) -> None:
        pass


class NvimStatePlugin(NvimPlugin):

    @abc.abstractproperty
    def state(self) -> StateMachine:
        ...

    @property
    def default_sync(self) -> bool:
        return False

__all__ = ('NvimPlugin', 'NvimStatePlugin')
