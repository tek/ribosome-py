from typing import Callable

from kallikrein import Expectation

from amino import IO, Do, do

from ribosome.nvim.io.compute import NvimIO
from ribosome.test.config import TestConfig
from ribosome.nvim.api.data import StrictNvimApi
from ribosome.test.run import run_test_io
from ribosome.nvim.io.api import N
from ribosome.test.prog import init_test_state


def setup_strict_test_nvim(config: TestConfig) -> StrictNvimApi:
    return StrictNvimApi.cons('unit', vars=config.vars)


def unit_test(config: TestConfig, io: Callable[[], NvimIO[Expectation]]) -> Expectation:
    initial_nvim = setup_strict_test_nvim(config)
    @do(NvimIO[Expectation])
    def run() -> Do:
        state = yield init_test_state(config)
        yield io().run_a(state)
    return run_test_io(N.to_io_a, run(), initial_nvim)


__all__ = ('unit_test',)
