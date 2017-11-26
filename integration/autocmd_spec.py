from kallikrein import Expectation

from ribosome.plugin import PluginSettings
from ribosome.config import SimpleData
from ribosome.test.integration.klk import AutoPluginIntegrationKlkSpec

from integration._support.autocmd import val


class AutoPluginSpec(AutoPluginIntegrationKlkSpec[PluginSettings, SimpleData]):
    '''
    zero-setup plugin $auto_plugin
    '''

    @property
    def plugin_prefix(self) -> str:
        return 'plug'

    def module(self) -> str:
        return 'integration._support.autocmd'

    def _pre_start(self) -> None:
        super()._pre_start()
        self.vim.vars.set_p('components', ['core'])

    def auto_plugin(self) -> Expectation:
        self.vim.cmd_once_defined('PlugStage1')
        self.cmd_sync('Msg1')
        self.vim.doautocmd('VimResized')
        return self.var_becomes('msg_cmd_success', val) & self.var_becomes('autocmd_success', val)

__all__ = ('AutoPluginSpec',)
