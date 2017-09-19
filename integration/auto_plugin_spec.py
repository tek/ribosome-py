from kallikrein import Expectation

from amino import Map

from ribosome.plugin import Config, PluginSettings
from ribosome.machine.message_base import message
from ribosome.machine.state import SubTransitions
from ribosome.machine import trans
from ribosome.machine.messages import Stage1
from ribosome.settings import RequestHandlers, RequestHandler, Plain
from ribosome.nvim import NvimIO
from ribosome.test.integration.klk import AutoPluginIntegrationKlkSpec

Msg = message('Msg')


class Env(AutoData):
    pass


class Core(SubTransitions):

    @trans.unit(Stage1)
    def stage_1(self) -> None:
        pass

    @trans.unit(Msg, trans.nio)
    def msg1(self) -> NvimIO[None]:
        return NvimIO(lambda v: v.vars.set('success', 1))


class APSettings(PluginSettings):
    pass


auto_config = Config(
    name='plug',
    prefix='plug',
    state_type=Env,
    plugins=Map(core=Core),
    settings=APSettings(),
    request_handlers=RequestHandlers.cons(
        RequestHandler.msg_cmd(Msg)('msg', prefix=Plain, sync=True)
    ),
)


class AutoPluginSpec(AutoPluginIntegrationKlkSpec[APSettings, Env]):
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
        self.cmd_sync('Msg')
        return self.var_becomes('success', 1)

__all__ = ('AutoPluginSpec',)
