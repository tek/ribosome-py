import neovim  # type: ignore

from trypnv.nvim import Log, NvimFacade
from trypnv.cmd import command


@neovim.plugin
class NvimPlugin(object):

    def __init__(self, vim: NvimFacade) -> None:
        self.vim = vim
        Log._vim = vim

__all__ = ['Plugin', 'command', 'NvimFacade']
