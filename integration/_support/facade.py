from ribosome import command, function, NvimStatePlugin

from amino import List
from ribosome.logging import Logging


class FacadeTestPlugin(NvimStatePlugin, Logging):

    @function()
    def all_vars(self):
        return self.vim.buffer.vars.all

    @command(sync=True)
    def go(self):
        pass

__all__ = ('FacadeTestPlugin',)
