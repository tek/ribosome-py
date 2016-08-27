from amino import Right
from amino.test import later

from ribosome.test import PluginIntegrationSpec

from integration._support.plugin import TestPlugin


class PluginSpec(PluginIntegrationSpec):

    @property
    def plugin_class(self):
        return Right(TestPlugin)

    def _last_output(self, content):
        later(lambda: self._log_out.last.should.contain(content))

    def startup(self):
        i = 99932
        fun_text = 'message function test'
        self.vim.cmd_sync('Go')
        val = TestPlugin.test_value.format(i)
        self.vim.call('Value', i).to_maybe.should.contain(val)
        self._last_output(TestPlugin.test_go)
        val2 = TestPlugin.test_fun.format(i)
        self.vim.call('Fun', i).to_maybe.should.contain(val2)
        self.vim.call('MsgFun', fun_text)
        self._last_output(fun_text)
        self.vim.cmd_sync('Err')
        self._last_output(TestPlugin.test_error)

__all__ = ('PluginSpec',)
