from trypnv import NvimPlugin, command
from trypnv.logging import Logging


class TestPlugin(NvimPlugin, Logging):
    test_msg = 'TestPlugin test message'

    @command(sync=True)
    def go(self):
        self.log.info(self.test_msg)

__all__ = ('TestPlugin',)
