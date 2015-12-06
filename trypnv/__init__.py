import neovim  # type: ignore

from trypnv.nvim import Log
from trypnv.cmd import command


class NvimPlugin(object):

    def __init__(self, vim: neovim.Nvim) -> None:
        self.vim = vim
        Log._vim = vim

__all__ = ['Plugin', 'command']
