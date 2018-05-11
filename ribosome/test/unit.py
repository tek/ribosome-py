from typing import Callable, Any

from kallikrein import Expectation

from amino import Do, do
from amino.lenses.lens import lens

from ribosome.nvim.io.compute import NvimIO
from ribosome.test.config import TestConfig
from ribosome.nvim.api.data import StrictNvimApi
from ribosome.test.run import run_test_io
from ribosome.nvim.io.api import N
from ribosome.test.prog import init_test_state
from ribosome.nvim.io.state import NS
from ribosome.data.plugin_state import PS
from ribosome.test.request import StrictRequestHandler


def setup_strict_test_nvim(config: TestConfig) -> StrictNvimApi:
    handler = StrictRequestHandler(config.request_handler, config.function_handler, config.command_handler)
    return StrictNvimApi.cons(config.config.basic.name, vars=config.vars, request_handler=handler)


def unit_test(config: TestConfig, io: Callable[..., NS[PS, Expectation]], *a: Any, **kw: Any) -> Expectation:
    initial_nvim = setup_strict_test_nvim(config)
    @do(NvimIO[Expectation])
    def run() -> Do:
        state = yield init_test_state(config)
        yield io(*a, **kw).run_a(state)
    return run_test_io(N.to_io_a, run(), initial_nvim)


def update_data(**kw: Any) -> NS[PS, None]:
    return NS.modify(lens.data.modify(lambda a: a.copy(**kw)))


__all__ = ('unit_test', 'update_data',)
