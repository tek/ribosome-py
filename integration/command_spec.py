from kallikrein import Expectation, k

from amino import do, Do
from amino.test.spec import SpecBase

from ribosome.nvim.api.command import nvim_command, nvim_command_output
from ribosome.nvim.io.compute import NvimIO
from ribosome.test.integration.embed import plugin_test, TestConfig
from ribosome.nvim.api.variable import variable_set_prefixed
from ribosome.test.klk.matchers.variable import var_must_become

from integration._support.command import command_spec_config, val


@do(NvimIO[None])
def pre() -> Do:
    yield variable_set_prefixed('components', ['core'])


@do(NvimIO[Expectation])
def command_spec() -> Do:
    yield nvim_command('PlugTransCmd')
    yield var_must_become('command_success', val)


test_config = TestConfig.cons(command_spec_config, pre)


class CommandSpec(SpecBase):
    '''
    execute a command $command
    '''

    def command(self) -> Expectation:
        return plugin_test(test_config, command_spec)


__all__ = ('CommandSpec',)
