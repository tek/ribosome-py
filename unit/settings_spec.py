from kallikrein import Expectation, k

from ribosome.nvim.api.variable import variable_set

from amino import do, Do
from ribosome.nvim.api.command import command_once_defined
from ribosome.test.integration.default import ExternalSpec
from ribosome.nvim.io.compute import NvimIO
from ribosome.test.integration.run import DispatchHelper

from integration._support.settings import config


class SettingsSpec(ExternalSpec):
    '''
    update a setting $update
    '''

    def plugin_name(self) -> str:
        return 'plug'

    def _pre_start(self) -> None:
        super()._pre_start()
        variable_set('counter', 7).unsafe(self.vim)
        variable_set('inc', 14).unsafe(self.vim)

    def update(self) -> Expectation:
        helper = DispatchHelper.nvim(config, self.vim)
        @do(NvimIO[None])
        def run() -> Do:
            s = yield helper.run_s('command:check', args=())
        result = run().unsafe(self.vim)
        return k(1) == 1


__all__ = ('SettingsSpec',)
