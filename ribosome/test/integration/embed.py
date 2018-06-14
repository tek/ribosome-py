from typing import Callable, Any

from kallikrein import Expectation

from amino import do, Do, IO, Lists
from amino.logging import module_log
from amino.string.hues import green

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.io.api import N
from ribosome.nvim.api.rpc import nvim_quit
from ribosome.nvim.io.data import NResult
from ribosome.test.config import TestConfig
from ribosome.test.integration.rpc import setup_test_nvim_embed, set_nvim_vars
from ribosome.test.run import run_test_io, plugin_started
from ribosome.test.integration.start import start_plugin_embed

log = module_log()


def cleanup(config: TestConfig) -> Callable[[NResult], NvimIO[None]]:
    @do(NvimIO[None])
    def cleanup(result: NResult) -> Do:
        yield nvim_quit()
        runtime_log = yield N.from_io(IO.delay(config.log_file.read_text))
        if runtime_log:
            log.info(green('plugin output:'))
            Lists.lines(runtime_log) % log.info
            log.info('')
    return cleanup


def plugin_test(config: TestConfig, io: Callable[..., NvimIO[Expectation]], *a: Any, **kw: Any) -> Expectation:
    @do(NvimIO[None])
    def run_nvim_io() -> Do:
        yield set_nvim_vars(config.vars + ('components', config.components))
        yield config.pre()
        if config.autostart:
            yield start_plugin_embed(config)
            yield plugin_started()
        yield io(*a, **kw)
    @do(IO[Expectation])
    def run() -> Do:
        nvim = yield setup_test_nvim_embed(config)
        yield N.to_io_a(N.ensure(run_nvim_io(), cleanup(config)), nvim.api)
    return run_test_io(run)


__all__ = ('plugin_test',)
