from amino import Right, List
from amino.test import later

from ribosome.test import PluginIntegrationSpec

from integration._support.plugin import TestPlugin


class PluginSpec(PluginIntegrationSpec):

    @property
    def plugin_class(self):
        return Right(TestPlugin)

    def startup(self):
        i = 99932
        fun_text = 'message function test'
        self.vim.cmd_sync('Go')
        val = TestPlugin.test_value.format(i)
        self.vim.call('Value', i).to_maybe.should.contain(val)
        later(lambda: self._log_out.should.equal(List(TestPlugin.test_go)))
        val2 = TestPlugin.test_fun.format(i)
        self.vim.call('Fun', i).to_maybe.should.contain(val2)
        self.vim.call('MsgFun', fun_text)
        later(lambda: self._log_out.last.should.contain(fun_text))

__all__ = ('PluginSpec',)
