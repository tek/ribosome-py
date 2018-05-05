from kallikrein import Expectation

from amino import do, Do
from amino.test.spec import SpecBase
from ribosome.nvim.api.variable import variable_set
from ribosome.nvim.api.exists import command_once_defined
from ribosome.test.klk.matchers.variable import var_must_become
from ribosome.nvim.io.compute import NvimIO
from ribosome.test.integration.embed import TestConfig, plugin_test

from integration._support.settings import settings_spec_config


@do(NvimIO[Expectation])
def settings_spec() -> Do:
    yield command_once_defined('PlugCheck')
    yield var_must_become('counter', 21)


@do(NvimIO[None])
def pre() -> Do:
    yield variable_set('counter', 7)
    yield variable_set('inc', 14)


test_config = TestConfig.cons(settings_spec_config, pre=pre)


class SettingsSpec(SpecBase):
    '''
    update a setting $update
    '''

    def update(self) -> Expectation:
        return plugin_test(test_config, settings_spec)


__all__ = ('SettingsSpec',)
