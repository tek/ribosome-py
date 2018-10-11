from kallikrein import k, Expectation
from kallikrein.matchers.maybe import be_just

from amino import List, do, Do, Dat, Nothing, Maybe
from amino.test.spec import SpecBase

from ribosome.config.config import Config, NoData
from ribosome.compute.api import prog
from ribosome.rpc.api import rpc
from ribosome.nvim.io.state import NS
from ribosome.test.integration.embed import TestConfig, plugin_test
from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.function import nvim_call_function
from ribosome.nvim.io.api import N


class A(Dat['A']):

    def __init__(self, i: int) -> None:
        self.i = i


@prog
@do(NS[NoData, A])
def error() -> Do:
    yield NS.pure(A(1))


config: Config = Config.cons(
    'pack',
    rpc=List(
        rpc.write(error).conf(sync=True),
    ),
    internal_component=False,
)
test_config = TestConfig.cons(config)


@do(NvimIO[Expectation])
def pack_error_spec() -> Do:
    error = yield N.recover_failure(
        nvim_call_function('PackError').replace(Nothing),
        lambda a: N.pure(Maybe.optional(a)),
    )
    return k(error).must(be_just)


class UvSpec(SpecBase):
    '''
    packing error $packing_error
    '''

    def packing_error(self) -> Expectation:
        return plugin_test(test_config, pack_error_spec)


__all__ = ('UvSpec',)
