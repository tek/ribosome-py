from amino import Right
from amino.test import later

from integration._support.plugin import (TestPluginLooped, TestPlugin,
                                         TestPluginUnlooped)
from integration._support.base import IntegrationSpecBase


class _PluginSpecBase(IntegrationSpecBase):

    def _last_output(self, content):
        later(lambda: self._log_out.last.should.contain(content), timeout=1)

    def _startup(self):
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

    def _scratch(self):
        self.vim.cmd_sync('Go')
        self.vim.cmd_sync('Scratch')
        later(lambda: self.vim.windows.length.should.equal(2))
        self.vim.cmd_sync('CheckScratch')
        self._last_output('1')
        self.vim.cmd_sync('ScratchTest')
        self._last_output(TestPlugin.test_scratch)
        self.vim.window.close()
        later(lambda: self.vim.windows.length.should.equal(1))
        self.vim.cmd_sync('CheckScratch')
        self._last_output('0')


class LoopedPluginSpec(_PluginSpecBase):

    @property
    def plugin_class(self):
        return Right(TestPluginLooped)

    def startup(self):
        self._startup()

    def scratch(self):
        self._scratch()


class _UnloopedPluginSpec(_PluginSpecBase):

    @property
    def plugin_class(self):
        return Right(TestPluginUnlooped)

    def startup(self):
        self._startup()

    def scratch(self):
        self._scratch()

__all__ = ('LoopedPluginSpec',)
