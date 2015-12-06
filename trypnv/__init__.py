from trypnv.nvim import Log, NvimFacade
from trypnv.cmd import command


class NvimPlugin(object):

    def __init__(self, vim: NvimFacade) -> None:
        self.vim = vim
        Log._vim = vim

__all__ = ['Plugin', 'command', 'NvimFacade']
