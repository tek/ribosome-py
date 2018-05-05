from kallikrein import k, Expectation

from amino import List, do, Do
from amino.test.spec import SpecBase

from ribosome.config.config import Config, NoData
from ribosome.compute.api import prog
from ribosome.rpc.api import rpc
from ribosome.nvim.io.state import NS
from ribosome.test.integration.embed import TestConfig, plugin_test
from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.function import nvim_call_function

val = 'result value'


@prog
@do(NS[NoData, str])
def test() -> Do:
    yield NS.pure(val)


config: Config = Config.cons(
    'function',
    rpc=List(
        rpc.write(test).conf(sync=True),
    ),
    internal_component=False,
)
test_config = TestConfig.cons(config)


@do(NvimIO[Expectation])
def function_spec() -> Do:
    r = yield nvim_call_function('FunctionTest')
    return k(r) == val


class FunctionSpec(SpecBase):
    '''
    call a function $function
    '''

    def function(self) -> Expectation:
        return plugin_test(test_config, function_spec)


__all__ = ('FunctionSpec',)
