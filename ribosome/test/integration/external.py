from typing import Callable

from kallikrein import Expectation, k
from kallikrein.matchers.either import be_right
from kallikrein.matchers.match_with import match_with

from amino import do, IO, Do, List, Just, Nil

from ribosome.test.klk.matchers.nresult import nsuccess
from ribosome.nvim.io.compute import NvimIO
from ribosome.test.integration.embed import setup_test_nvim, TestConfig
from ribosome.nvim.api.rpc import nvim_quit
from ribosome.nvim.io.api import N
from ribosome.nvim.io.data import NResult
from ribosome.data.plugin_state import PS
from ribosome.nvim.io.state import NS
from ribosome.components.internal.update import init_rpc
from ribosome.test.prog import init_test_state


@do(NvimIO[PS])
def init_state(config: TestConfig, components: List[str]=Nil) -> Do:
    state = yield init_test_state()
    yield init_rpc(Just(config.components)).run_s(state)


@do(NvimIO[None])
def cleanup(result: NResult) -> Do:
    '''for some reason, the loop gets stuck if `quit` is called only once.
        '''
    yield nvim_quit()
    yield nvim_quit()


@do(NvimIO[Expectation])
def run_test(config: TestConfig, io: Callable[[], NS[PS, Expectation]]) -> Do:
    yield config.pre()
    engine = yield init_state(config)
    yield io().run_a(engine)


def external_state_test(config: TestConfig, io: Callable[[], NS[PS, Expectation]]) -> Expectation:
    @do(IO[Expectation])
    def run() -> Do:
        nvim = yield setup_test_nvim(config)
        return N.ensure(run_test(config, io), cleanup).run_a(nvim.api)
    return k(run().attempt).must(be_right(nsuccess(match_with(lambda a: a))))


def external_test(config: TestConfig, io: Callable[[], NvimIO[Expectation]]) -> Expectation:
    return external_state_test(config, lambda: NS.lift(io()))


__all__ = ('external_test', 'external_state_test',)
