from kallikrein import Expectation

from ribosome.test.integration.klk import AutoPluginIntegrationKlkSpec
from ribosome.config.config import NoData
from ribosome.config.settings import Settings
from ribosome.nvim.api.variable import variable_set_prefixed
from ribosome.nvim.api.command import doautocmd

from integration._support.autocmd import val


class AutocmdSpec(AutoPluginIntegrationKlkSpec[Settings, NoData]):
    '''
    execute handler when triggering an autocmd $autocmd
    '''

    def plugin_name(self) -> str:
        return 'plug'

    def module(self) -> str:
        return 'integration._support.autocmd'

    def _pre_start(self) -> None:
        super()._pre_start()
        variable_set_prefixed('components', ['core']).unsafe(self.vim)

    def autocmd(self) -> Expectation:
        self._wait(2)
        doautocmd('VimResized').unsafe(self.vim)
        return self.var_becomes('autocmd_success', val)


__all__ = ('AutocmdSpec',)
