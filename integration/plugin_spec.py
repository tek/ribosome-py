from tryp import Right, List

from trypnv.test import VimIntegrationSpec

from integration._support.plugin import TestPlugin


class PluginSpec(VimIntegrationSpec):

    @property
    def plugin_class(self):
        return Right(TestPlugin)

    def startup(self):
        i = 99932
        self.vim.cmd_sync('Go')
        val = TestPlugin.test_value.format(i)
        self.vim.call('Value', i).should.contain(val)
        self._log_out.should.equal(List(TestPlugin.test_go))

__all__ = ('PluginSpec',)
