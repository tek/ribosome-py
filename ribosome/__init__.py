in_vim = True

from ribosome.nvim import NvimFacade
from ribosome.plugin import NvimStatePlugin, NvimPlugin, AutoPlugin
from ribosome.request.command import command
from ribosome.request.function import function

__all__ = ('command', 'NvimFacade', 'NvimStatePlugin', 'NvimPlugin', 'in_vim', 'function', 'AutoPlugin')
