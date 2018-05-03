from kallikrein import Expectation, k

from ribosome.nvim.api.variable import variable_set, variable_num

from amino import do, Do, Nil
from amino.test.spec import SpecBase
from ribosome.nvim.io.compute import NvimIO
from ribosome.test.integration.external import request, external_test
from ribosome.test.integration.embed import TestConfig
from ribosome.nvim.io.state import NS

from integration._support.settings import config


@do(NS[None, None])
def update_setting_spec() -> Do:
    yield request('check', args=Nil)
    n = yield NS.lift(variable_num('counter'))
    return k(n) == 21


@do(NvimIO[None])
def pre() -> Do:
    yield variable_set('counter', 7)
    yield variable_set('inc', 14)


test_config = TestConfig.cons(config, pre=pre)


class SettingsSpec(SpecBase):
    '''
    update a setting $update
    '''

    def update(self) -> Expectation:
        return external_test(test_config, update_setting_spec)


__all__ = ('SettingsSpec',)
