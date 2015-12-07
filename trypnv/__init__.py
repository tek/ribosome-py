import abc

from trypnv.nvim import Log, NvimFacade
from trypnv.cmd import command, msg_command
from trypnv.machine import Machine, StateMachine

development = False


class NvimPlugin(object):

    def __init__(self, nvim: NvimFacade) -> None:
        self.vim = nvim
        Log._vim = nvim


class NvimStatePlugin(NvimPlugin):

    @abc.abstractmethod
    def state(self) -> StateMachine:
        ...

__all__ = ['Plugin', 'command', 'NvimFacade', 'Machine', 'StateMachine',
           'development', 'NvimStatePlugin', 'msg_command']
