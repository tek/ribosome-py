from typing import Any, Tuple

from amino import do, Do, IO, List, Dat, Map, Path
from amino.test import temp_dir
from amino.test.path import pkg_dir
from amino.env_vars import set_env

from ribosome import NvimApi
from ribosome.rpc.uv.uv import cons_uv_embed, cons_uv_socket
from ribosome.rpc.start import start_external
from ribosome.rpc.comm import Comm
from ribosome.test.config import TestConfig
from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.variable import variable_set

nvim_cmdline = List('nvim', '-n', '-u', 'NONE')
env_vars = List(
    ('RIBOSOME_SPEC', 1),
    ('AMINO_DEVELOPMENT', 1),
    ('RIBOSOME_PKG_DIR', str(pkg_dir())),
    ('RIBOSOME_FILE_LOG_FMT', '{levelname} {name}:{message}')
)


def test_env_vars(config: TestConfig) -> List[Tuple[str, Any]]:
    return env_vars.cat(('RIBOSOME_LOG_FILE', str(config.log_file)))


class TestNvim(Dat['TestNvim']):

    def __init__(self, comm: Comm, api: NvimApi) -> None:
        self.comm = comm
        self.api = api


@do(IO[None])
def setup_env(config: TestConfig) -> Do:
    yield test_env_vars(config).traverse2(set_env, IO)
    yield IO.delay(config.log_dir.mkdir, exist_ok=True, parents=True)
    yield IO.delay(config.log_file.touch)
    yield set_env('RIBOSOME_LOG_FILE', str(config.log_file))


def start_uv_embed(config: TestConfig) -> IO[NvimApi]:
    ''' start an embedded vim session that loads no init.vim.
    `_temp/log/vim` is set as log file. aside from being convenient, this is crucially necessary, as the first use of
    the session will block if stdout is used for output.
    '''
    log = temp_dir('log') / 'vim'
    argv = nvim_cmdline + List('--embed', f'-V{log}')
    uv, rpc_comm = cons_uv_embed(argv)
    return start_external(config.config.basic.name, rpc_comm)


def start_uv_socket(config: TestConfig, socket: Path) -> IO[NvimApi]:
    uv, rpc_comm = cons_uv_socket(socket)
    return start_external(config.config.basic.name, rpc_comm)


@do(IO[TestNvim])
def setup_test_nvim_embed(config: TestConfig) -> Do:
    yield setup_env(config)
    api = yield start_uv_embed(config)
    return TestNvim(api.comm, api)


@do(IO[TestNvim])
def setup_test_nvim_socket(config: TestConfig, socket: Path) -> Do:
    yield setup_env(config)
    api = yield start_uv_socket(config, socket)
    return TestNvim(api.comm, api)


def set_nvim_vars(vars: Map[str, Any]) -> NvimIO[None]:
    return vars.to_list.traverse2(variable_set, NvimIO)


__all__ = ('TestNvim', 'setup_test_nvim_embed', 'set_nvim_vars',)
