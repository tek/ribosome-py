from kallikrein import Expectation

from amino import Map, __, List

from ribosome.plugin import Config, PluginSettings
from ribosome.machine.message_base import message
from ribosome.machine.state import SubTransitions
from ribosome.machine import trans
from ribosome.machine.messages import Stage1
from ribosome.settings import RequestHandler, Plain, AutoData
from ribosome.nvim import NvimIO
from ribosome.test.integration.klk import AutoPluginIntegrationKlkSpec

Msg1 = message('Msg1')
Msg2 = message('Msg2')
val = 71


class Core(SubTransitions):

    @trans.unit(Stage1)
    def stage_1(self) -> None:
        pass

    @trans.unit(Msg1, trans.nio)
    def msg1(self) -> NvimIO[None]:
        return NvimIO(__.vars.set('msg_cmd_success', val))

    @trans.unit(Msg2, trans.nio)
    def msg2(self) -> NvimIO[None]:
        return NvimIO(__.vars.set('autocmd_success', val))


auto_config = Config(
    name='plug',
    plugins=Map(core=Core),
    request_handlers=List(
        RequestHandler.msg_cmd(Msg1)('msg1', prefix=Plain(), sync=True),
        RequestHandler.msg_autocmd(Msg2)('vim_resized', prefix=Plain())
    ),
)


class AutoPluginSpec(AutoPluginIntegrationKlkSpec[PluginSettings, AutoData]):
    '''
    zero-setup plugin $auto_plugin
    '''

    @property
    def _prefix(self) -> str:
        return 'plug'

    def module(self) -> str:
        return __name__

    def config_name(self) -> str:
        return 'auto_config'

    def _pre_start(self) -> None:
        super()._pre_start()
        self.vim.vars.set_p('components', ['core'])

    def auto_plugin(self) -> Expectation:
        self.vim.cmd_once_defined('PlugStage1')
        self.cmd_sync('Msg1')
        self.vim.doautocmd('VimResized')
        return self.var_becomes('msg_cmd_success', val) & self.var_becomes('autocmd_success', val)

__all__ = ('AutoPluginSpec',)
