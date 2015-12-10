import abc

from trypnv.nvim import NvimFacade
from trypnv.cmd import command, msg_command
from trypnv.machine import Machine, StateMachine
from trypnv.logging import nvim_logging


class NvimPlugin(object):

    def __init__(self, nvim: NvimFacade) -> None:
        self.vim = nvim
        self.setup_logging()

    def setup_logging(self):
        nvim_logging(self.vim)


class NvimStatePlugin(NvimPlugin):

    @abc.abstractmethod
    def state(self) -> StateMachine:
        ...

__all__ = ['Plugin', 'command', 'NvimFacade', 'Machine', 'StateMachine',
           'development', 'NvimStatePlugin', 'msg_command']
