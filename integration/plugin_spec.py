from amino import Right, List

from ribosome.test import PluginIntegrationSpec

from integration._support.plugin import TestPlugin


class PluginSpec(PluginIntegrationSpec):

    @property
    def plugin_class(self):
        return Right(TestPlugin)

    def startup(self):
        i = 99932
        self.vim.cmd_sync('Go')
        val = TestPlugin.test_value.format(i)
        self.vim.call('Value', i).to_maybe.should.contain(val)
        self._log_out.should.equal(List(TestPlugin.test_go))

__all__ = ('PluginSpec',)
