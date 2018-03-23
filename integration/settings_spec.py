from kallikrein import Expectation

from ribosome.test.integration.klk import AutoPluginIntegrationKlkSpec
from ribosome.config.config import NoData
from ribosome.config.settings import Settings
from ribosome.nvim.api.variable import variable_set
from ribosome.nvim.api.command import command_once_defined


class SettingsSpec(AutoPluginIntegrationKlkSpec[Settings, NoData]):
    '''
    update a setting $update
    '''

    def plugin_name(self) -> str:
        return 'plug'

    def module(self) -> str:
        return 'integration._support.settings'

    def _pre_start(self) -> None:
        super()._pre_start()
        variable_set('counter', 7).unsafe(self.vim)
        variable_set('inc', 14).unsafe(self.vim)

    def update(self) -> Expectation:
        command_once_defined('PlugCheck').unsafe(self.vim)
        self._wait(.5)
        return self.var_becomes('counter', 21)


__all__ = ('SettingsSpec',)
