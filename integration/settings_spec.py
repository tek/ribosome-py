from kallikrein import Expectation

from ribosome.test.integration.klk import AutoPluginIntegrationKlkSpec
from ribosome.config.config import SimpleData
from ribosome.config.settings import Settings


class SettingsSpec(AutoPluginIntegrationKlkSpec[Settings, SimpleData]):
    '''
    test $test
    '''

    @property
    def plugin_prefix(self) -> str:
        return 'plug'

    def module(self) -> str:
        return 'integration._support.settings'

    def _pre_start(self) -> None:
        super()._pre_start()
        self.vim.vars.set('counter', 7)
        self.vim.vars.set('inc', 14)

    def test(self) -> Expectation:
        self.vim.cmd_once_defined('PlugCheck')
        self._wait(.5)
        return self.var_becomes('counter', 21)

__all__ = ('SettingsSpec',)
