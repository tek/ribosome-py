from kallikrein import Expectation

from amino.test.spec import SpecBase
from amino import do, Do, List

from ribosome.nvim.api.command import doautocmd
from ribosome.test.integration.embed import TestConfig, plugin_test
from ribosome.nvim.io.compute import NvimIO
from ribosome.test.klk.matchers.variable import var_must_become

from integration._support.autocmd import val, autocmd_spec_config


test_config = TestConfig.cons(autocmd_spec_config, components=List('core'))


@do(NvimIO[Expectation])
def autocmd_spec() -> Do:
    yield doautocmd('VimResized')
    yield var_must_become('autocmd_success', val)


class AutocmdSpec(SpecBase):
    '''
    execute handler when triggering an autocmd $autocmd
    '''

    def autocmd(self) -> Expectation:
        return plugin_test(test_config, autocmd_spec)


__all__ = ('AutocmdSpec',)
