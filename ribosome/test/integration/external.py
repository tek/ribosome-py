from typing import Callable, Any

from kallikrein import Expectation

from amino import do, IO, Do

from ribosome.nvim.io.compute import NvimIO
from ribosome.test.integration.embed import setup_test_nvim_embed, TestConfig
from ribosome.nvim.api.rpc import nvim_quit
from ribosome.nvim.io.api import N
from ribosome.nvim.io.data import NResult
from ribosome.data.plugin_state import PS
from ribosome.nvim.io.state import NS
from ribosome.test.prog import init_test_state
from ribosome.test.run import run_test_io
from ribosome.test.integration.rpc import set_nvim_vars


@do(NvimIO[None])
def cleanup(result: NResult) -> Do:
    '''for some reason, the loop gets stuck if `quit` is called only once.
        '''
    yield nvim_quit()


@do(NvimIO[Expectation])
def run_test(config: TestConfig, io: Callable[..., NS[PS, Expectation]], *a: Any, **kw: Any) -> Do:
    yield set_nvim_vars(config.vars + ('components', config.components))
    yield config.pre()
    state = yield init_test_state(config)
    yield io(*a, **kw).run_a(state)


def external_state_test(config: TestConfig, io: Callable[..., NS[PS, Expectation]], *a: Any, **kw: Any) -> Expectation:
    @do(IO[Expectation])
    def run() -> Do:
        nvim = yield setup_test_nvim_embed(config)
        yield N.to_io_a(N.ensure(run_test(config, io, *a, **kw), cleanup), nvim.api)
    return run_test_io(run)


def external_test(config: TestConfig, io: Callable[..., NvimIO[Expectation]], *a: Any, **kw: Any) -> Expectation:
    return external_state_test(config, lambda: NS.lift(io()))


__all__ = ('external_test', 'external_state_test',)
