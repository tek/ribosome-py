import abc
import asyncio
from typing import Union

import neovim

from ribosome.nvim import NvimFacade
from ribosome.machine import StateMachine
from ribosome.logging import nvim_logging


class NvimPlugin(object):

    def __init__(self, nvim: Union[NvimFacade, neovim.Nvim]) -> None:
        if isinstance(nvim, neovim.Nvim):
            nvim = NvimFacade(nvim, self.name)
        self.vim = nvim
        self.setup_logging()

    def setup_logging(self):
        nvim_logging(self.vim)

    @property
    def loop(self):
        return self.vim.loop

    @property
    def name(self):
        return 'ribosome'

    def start_plugin(self):
        pass


class NvimStatePlugin(NvimPlugin):

    @abc.abstractproperty
    def state(self) -> StateMachine:
        ...

    @property
    def default_sync(self):
        return False

__all__ = ('NvimPlugin', 'NvimStatePlugin')
