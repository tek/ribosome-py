from kallikrein import Expectation, pending

from ribosome.test.integration.klk import AutoPluginIntegrationKlkSpec
from ribosome.config.config import NoData
from ribosome.config.settings import Settings

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
        self.vim.vars.set_p('components', ['core'])

    def autocmd(self) -> Expectation:
        self.vim.cmd_once_defined('PlugStage1')
        self.vim.doautocmd('VimResized')
        return self.var_becomes('autocmd_success', val)


__all__ = ('AutocmdSpec',)
