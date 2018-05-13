from kallikrein import Expectation

from amino import do, Do, List
from amino.test.spec import SpecBase

from ribosome.nvim.io.compute import NvimIO
from ribosome.test.integration.embed import plugin_test, TestConfig
from ribosome.test.klk.matchers.variable import var_must_become
from ribosome.nvim.api.function import nvim_call_function

from integration._support.command import command_spec_config, val


@do(NvimIO[Expectation])
def command_spec() -> Do:
    yield nvim_call_function('PlugProgCmd')
    yield var_must_become('command_success', val)


test_config = TestConfig.cons(command_spec_config, components=List('core'))


class CommandSpec(SpecBase):
    '''
    execute a command $command
    '''

    def command(self) -> Expectation:
        return plugin_test(test_config, command_spec)


__all__ = ('CommandSpec',)
