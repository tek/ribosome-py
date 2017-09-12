from amino import Right, Either

from kallikrein import Expectation, unsafe_k
from kallikrein.matchers.either import be_right
from kallikrein.matchers.maybe import be_just
from kallikrein.matchers.end_with import end_with

from integration._support.plugin import TestPluginLooped, TestPlugin, TestPluginUnlooped
from integration._support.base import IntegrationSpecBase

specs = '''\
plugin with {}
simple commands producing output $startup
launch a scratch buffer $scratch
execute coroutines in parallel $coros_parallel
execute IOs in parallel $ios_parallel
'''


class _PluginSpecBase(IntegrationSpecBase):

    def _last_output(self, content):
        return self._log_line(-1, be_just(end_with(content)))

    def _startup(self) -> Expectation:
        i = 99932
        fun_text = 'message function test'
        self.vim.cmd_sync('Go')
        val = TestPlugin.test_value.format(i)
        unsafe_k(self.vim.call('Value', i)).must(be_right(val))
        self._last_output(TestPlugin.test_go)
        val2 = TestPlugin.test_fun.format(i)
        unsafe_k(self.vim.call('Fun', i)).must(be_right(val2))
        self.vim.call('MsgFun', fun_text)
        self._last_output(fun_text)
        self.vim.cmd_sync('Err')
        self._last_output(TestPlugin.test_error)
        self.vim.cmd_sync('St')
        self._wait(1)
        return self._last_output('6')

    def _scratch(self) -> Expectation:
        self.vim.cmd_sync('Go')
        self.vim.cmd_sync('Scratch')
        self._window_count(2)
        self.vim.cmd_sync('CheckScratch')
        self._last_output('1')
        self.vim.cmd_sync('ScratchTest')
        self._last_output(TestPlugin.test_scratch)
        self.vim.window.close()
        self._window_count(1)
        self.vim.cmd_sync('CheckScratch')
        return self._last_output('0')

    def _coros_parallel(self) -> Expectation:
        self.vim.cmd_sync('Go')
        self.vim.cmd_sync('RunParallel')
        self._log_contains('sleeping in 2')
        self._log_contains('sleeping in 1')
        return self._log_contains('sleeping in 0')

    def _ios_parallel(self) -> Expectation:
        self.vim.cmd_sync('Go')
        self.vim.cmd_sync('RunParallelIOs')
        self._log_contains('sleeping in 2')
        self._log_contains('sleeping in 1')
        return self._log_contains('sleeping in 0')


class LoopedPluginSpec(_PluginSpecBase):
    __doc__ = specs.format('permanent main loop thread')

    @property
    def plugin_class(self) -> Either[str, type]:
        return Right(TestPluginLooped)

    def startup(self) -> Expectation:
        return self._startup()

    def scratch(self) -> Expectation:
        return self._scratch()

    def coros_parallel(self) -> Expectation:
        return self._coros_parallel()

    def ios_parallel(self) -> Expectation:
        return self._ios_parallel()


class UnloopedPluginSpec(_PluginSpecBase):
    __doc__ = specs.format('on-demand main loop')

    @property
    def plugin_class(self) -> Either[str, type]:
        return Right(TestPluginUnlooped)

    def startup(self) -> Expectation:
        return self._startup()

    def scratch(self) -> Expectation:
        return self._scratch()

    def coros_parallel(self) -> Expectation:
        return self._coros_parallel()

    def ios_parallel(self) -> Expectation:
        return self._ios_parallel()

__all__ = ('LoopedPluginSpec', 'UnloopedPluginSpec')
