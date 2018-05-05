from kallikrein import Expectation

from amino import do, Do
from amino.test.spec import SpecBase

from ribosome.nvim.io.compute import NvimIO
from ribosome.test.integration.embed import plugin_test, TestConfig
from ribosome.nvim.api.variable import variable_set
from ribosome.test.klk.matchers.variable import var_must_become
from ribosome.config.config import Config
from ribosome.compute.api import prog
from ribosome.nvim.io.state import NS


@prog
@do(NS[None, None])
def init() -> Do:
    yield NS.lift(variable_set('init_success', 1))


init_spec_config: Config[None, None] = Config.cons(
    'init',
    init=init,
)


@do(NvimIO[Expectation])
def init_spec() -> Do:
    yield var_must_become('init_success', 1)


test_config = TestConfig.cons(init_spec_config)


class InitSpec(SpecBase):
    '''
    execute the init program $init
    '''

    def init(self) -> Expectation:
        return plugin_test(test_config, init_spec)


__all__ = ('InitSpec',)
