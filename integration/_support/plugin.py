import neovim

from ribosome import NvimPlugin, command
from ribosome.logging import Logging


class TestPlugin(NvimPlugin, Logging):
    test_go = 'TestPlugin test message'
    test_value = 'test value {}'

    @neovim.function('Value', sync=True)
    def value(self, args):
        return self.test_value.format(args[0])

    @command(sync=True)
    def go(self):
        self.log.info(self.test_go)

__all__ = ('TestPlugin',)
