import abc
import asyncio
from typing import Union

import neovim

from trypnv.nvim import NvimFacade
from trypnv.machine import StateMachine
from trypnv.logging import nvim_logging


class NvimPlugin(object):

    def __init__(self, nvim: Union[NvimFacade, neovim.Nvim]) -> None:
        if isinstance(nvim, neovim.Nvim):
            nvim = NvimFacade(nvim, 'trypnv')
        self.vim = nvim
        self.setup_logging()
        self.setup_asyncio()

    def setup_logging(self):
        nvim_logging(self.vim)

    def setup_asyncio(self):
        ''' this ensures that the child process watcher is running on
        the main thread, which is necessary for subprocess to be waited
        for, as python can only catch SIG_CHLD on the main thread.
        additionally, an event loop must be executed on the main thread
        during waiting.
        '''
        asyncio.get_child_watcher()

    @property
    def loop(self):
        return self.vim.loop


class NvimStatePlugin(NvimPlugin):

    @abc.abstractmethod
    def state(self) -> StateMachine:
        ...


__all__ = ('NvimPlugin', 'NvimStatePlugin')
