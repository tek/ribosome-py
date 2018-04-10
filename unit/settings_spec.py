from kallikrein import Expectation
from kallikrein.matchers import contain

from ribosome.nvim.api.variable import variable_set, variable_num

from amino import do, Do
from ribosome.test.integration.default import ExternalSpec
from ribosome.nvim.io.compute import NvimIO
from ribosome.test.integration.run import RequestHelper
from ribosome.test.klk import kn

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
        helper = RequestHelper.nvim(config, self.vim)
        @do(NvimIO[None])
        def run() -> Do:
            s = yield helper.run_s('command:check', args=())
            yield variable_num('counter')
        return kn(helper.vim, run).must(contain(21))


__all__ = ('SettingsSpec',)
