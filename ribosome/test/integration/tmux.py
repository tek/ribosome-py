from typing import Callable, Any, Tuple
import subprocess

from kallikrein import Expectation

from chiasma.tmux import Tmux
from chiasma.test.tmux_spec import tmux_spec_socket
from chiasma.io.compute import TmuxIO
from chiasma.commands.server import kill_server
from chiasma.test.terminal import start_tmux
from chiasma.commands.pane import send_keys

from amino import do, Do, IO, Lists, List
from amino.logging import module_log
from amino.string.hues import green

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.io.api import N
from ribosome.nvim.api.rpc import nvim_quit
from ribosome.nvim.api.variable import pvar_becomes, variable_set_prefixed
from ribosome.nvim.io.data import NResult
from ribosome.test.config import TestConfig
from ribosome.test.integration.rpc import setup_test_nvim, nvim_cmdline, env_vars, set_nvim_vars
from ribosome.test.run import run_test_io
from ribosome.test.integration.embed import start_plugin_embed

from myo.tmux.io import tmux_to_nvim

log = module_log()

# if 'VIRTUAL_ENV' in env:
#     send_keys(0, List(f'source $VIRTUAL_ENV/bin/activate')).unsafe(self.tmux)
# send_keys(0, List(cmd.join_tokens)).unsafe(self.tmux)
# wait_for(Path(self.nvim_socket).is_socket)
# self.neovim = neovim.attach('socket', path=self.nvim_socket)
# self.neovim.command('python3 sys.path.insert(0, \'{}\')'.format(self.python_path))
# self.vim = self.create_nvim_api(self.neovim)


@do(IO[Tuple[subprocess.Popen, Tmux, Any]])
def setup_tmux(width: int, height: int) -> Do:
    proc = yield IO.delay(start_tmux, tmux_spec_socket, width, height, True)
    tmux = Tmux.cons(tmux_spec_socket)
    yield IO.sleep(.5)
    clients_tio = TmuxIO.read('list-clients -F "#{client_name}"')
    cmd = yield IO.delay(clients_tio.unsafe, tmux)
    client = yield IO.from_maybe(cmd.head, 'no clients')
    return proc, tmux, client


@do(IO[None])
def cleanup_tmux(proc: subprocess.Popen, tmux: Tmux) -> Do:
    yield IO.delay(proc.kill)
    yield IO.delay(proc.wait)
    yield IO.delay(kill_server().result, tmux)


def tmux_pre(pre: Callable[[], NvimIO[None]], tmux_width: int, tmux_height: int) -> Callable[[], NvimIO[None]]:
    @do(NvimIO[None])
    def tmux_pre() -> Do:
        yield N.from_io(setup_tmux)
        yield pre()
    return tmux_pre


@do(NvimIO[None])
def start_plugin(config: TestConfig) -> Do:
    env_args = env_vars.map2(lambda k, v: f'{k}=\'{v}\'').cons('env')
    cmd = env_args + nvim_cmdline
    yield tmux_to_nvim(send_keys(0, List(cmd.join_tokens)))
    yield start_plugin_embed(config)


def cleanup(config: TestConfig, proc: subprocess.Popen, tmux: Tmux) -> Callable[[NResult], NvimIO[None]]:
    @do(NvimIO[None])
    def cleanup(result: NResult) -> Do:
        yield N.ignore_failure(nvim_quit())
        yield N.ignore_failure(nvim_quit())
        yield N.ignore_failure(N.from_io(cleanup_tmux(proc, tmux)))
        runtime_log = yield N.from_io(IO.delay(config.log_file.read_text))
        if runtime_log:
            log.info(green('plugin output:'))
            Lists.lines(runtime_log) % log.info
            log.info('')
    return cleanup


def tmux_plugin_test(config: TestConfig, io: Callable[..., NvimIO[Expectation]], *a: Any, **kw: Any) -> Expectation:
    @do(NvimIO[None])
    def run_nvim_io() -> Do:
        yield set_nvim_vars(config.vars + ('components', config.components))
        yield config.pre()
        yield start_plugin(config)
        yield pvar_becomes('started', True)
        yield io(*a, **kw)
    @do(IO[Expectation])
    def run() -> Do:
        proc, tmux, client = yield setup_tmux(300, 120)
        nvim = yield setup_test_nvim(config)
        yield N.to_io_a(N.ensure(run_nvim_io(), cleanup(config, proc, tmux)), nvim.api)
    return run_test_io(run)


__all__ = ('tmux_plugin_test',)
