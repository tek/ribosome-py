from typing import Callable, Any, Tuple
import subprocess

from kallikrein import Expectation

from chiasma.tmux import Tmux
from chiasma.test.tmux_spec import tmux_spec_socket
from chiasma.io.compute import TmuxIO
from chiasma.commands.server import kill_server
from chiasma.test.terminal import start_tmux
from chiasma.commands.pane import send_keys

from amino import do, Do, IO, Lists, List, Path, env
from amino.logging import module_log
from amino.string.hues import green
from amino.test import temp_dir
from amino.test.path import pkg_dir

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.io.api import N
from ribosome.nvim.api.rpc import nvim_quit
from ribosome.nvim.io.data import NResult
from ribosome.test.config import TestConfig
from ribosome.test.integration.rpc import nvim_cmdline, set_nvim_vars, setup_test_nvim_socket, test_env_vars
from ribosome.test.run import run_test_io, plugin_started
from ribosome.nvim.api.exists import wait_until_valid
from ribosome import NvimApi
from ribosome.test.integration.start import start_plugin_embed

log = module_log()


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


@do(TmuxIO[None])
def send_tmux_cmdline(cmdline: str) -> Do:
    if 'VIRTUAL_ENV' in env:
        yield send_keys(0, List(f'source $VIRTUAL_ENV/bin/activate'))
    yield send_keys(0, List(cmdline))


def tmux_env_vars(socket: Path) -> List[Tuple[str, str]]:
    global_path = env['PYTHONPATH'] | ''
    project_path = pkg_dir()
    python_path = f'{project_path}:{global_path}'
    return List(
        ('NVIM_LISTEN_ADDRESS', str(socket)),
        ('PYTHONPATH', python_path),
    )

@do(IO[NvimApi])
def setup_test_nvim_tmux(config: TestConfig, socket: Path, tmux: Tmux) -> Do:
    env_args = (test_env_vars(config) + tmux_env_vars(socket)).map2(lambda k, v: f'{k}=\'{v}\'').cons('env')
    cmd = env_args + nvim_cmdline
    yield IO.delay(send_tmux_cmdline(cmd.join_tokens).run, tmux)
    yield N.to_io_a(wait_until_valid('nvim_socket', lambda n: N.pure(socket.is_socket()), 3.), None)
    yield setup_test_nvim_socket(config, socket)


def cleanup(config: TestConfig, proc: subprocess.Popen, tmux: Tmux) -> Callable[[NResult], NvimIO[None]]:
    @do(NvimIO[None])
    def cleanup(result: NResult) -> Do:
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
        yield start_plugin_embed(config)
        yield plugin_started()
        yield io(*a, **kw)
    @do(IO[Expectation])
    def run() -> Do:
        socket_dir = yield IO.delay(temp_dir, 'sockets', 'nvim')
        socket = socket_dir / Lists.random_alpha()
        proc, tmux, client = yield setup_tmux(300, 120)
        nvim = yield setup_test_nvim_tmux(config, socket, tmux)
        yield N.to_io_a(N.ensure(run_nvim_io(), cleanup(config, proc, tmux)), nvim.api)
    return run_test_io(run)


__all__ = ('tmux_plugin_test',)
