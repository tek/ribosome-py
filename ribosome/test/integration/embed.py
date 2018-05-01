from typing import Callable, Optional

from kallikrein import Expectation, k
from kallikrein.matchers.match_with import match_with
from kallikrein.matchers.either import be_right

from amino import do, Do, IO, List, Dat, Path, Lists, Nil
from amino.test import temp_dir
from amino.test.path import pkg_dir
from amino.env_vars import set_env
from amino.json import dump_json
from amino.logging import module_log
from amino.string.hues import green

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.io.api import N
from ribosome import NvimApi
from ribosome.rpc.uv.uv import cons_uv_embed
from ribosome.rpc.start import start_external
from ribosome.nvim.api.function import define_function, nvim_call_function
from ribosome.nvim.api.rpc import nvim_quit
from ribosome.config.config import Config
from ribosome.nvim.api.variable import pvar_becomes
from ribosome.nvim.io.data import NResult
from ribosome.test.klk.matchers.nresult import nsuccess
from ribosome.compute.interpret import ProgIOInterpreter
from ribosome.compute.program import Program
from ribosome.rpc.comm import Comm


log = module_log()
no_pre = lambda: N.unit


class TestConfig(Dat['TestConfig']):

    @staticmethod
    def cons(
            config: Config,
            pre: Callable[[], NvimIO[None]]=None,
            log_dir: Path=None,
            log_file: Path=None,
            components: List[str]=Nil,
            io_interpreter: ProgIOInterpreter=None,
            logger: Program[None]=None,
    ) -> 'TestConfig':
        ld = log_dir or temp_dir('log')
        lf = log_file or ld / config.basic.name
        return TestConfig(
            config,
            pre or no_pre,
            ld,
            lf,
            components,
            io_interpreter,
            logger,
        )

    def __init__(
            self,
            config: Config,
            pre: Callable[[], NvimIO[None]],
            log_dir: Path,
            log_file: Path,
            components: List[str],
            io_interpreter: Optional[ProgIOInterpreter],
            logger: Optional[Program[None]],
    ) -> None:
        self.config = config
        self.pre = pre
        self.log_dir = log_dir
        self.log_file = log_file
        self.components = components
        self.io_interpreter = io_interpreter
        self.logger = logger


class TestNvim(Dat['TestNvim']):

    def __init__(self, comm: Comm, api: NvimApi) -> None:
        self.comm = comm
        self.api = api


nvim_cmdline = List('nvim', '-n', '-u', 'NONE')


env_vars = List(
    ('RIBOSOME_SPEC', 1),
    ('AMINO_DEVELOPMENT', 1),
    ('RIBOSOME_PKG_DIR', str(pkg_dir())),
    ('RIBOSOME_FILE_LOG_FMT', '{levelname} {name}:{message}')
)


@do(IO[None])
def setup_env(config: TestConfig) -> Do:
    yield env_vars.traverse2(set_env, IO)
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


@do(IO[TestNvim])
def setup_test_nvim(config: TestConfig) -> Do:
    yield setup_env(config)
    api = yield start_uv_embed(config)
    return TestNvim(api.comm, api)


stderr_handler_name = 'RibosomeSpecStderr'
stderr_handler_body = '''
let err = substitute(join(a:data, '\\r'), '"', '\\"', 'g')
python3 import amino
python3 from ribosome.logging import ribosome_envvar_file_logging
python3 ribosome_envvar_file_logging()
execute 'python3 amino.amino_log.error(f"""error starting rpc job on channel ' . a:id . ':\\r' . err . '""")'
'''


@do(NvimIO[None])
def start_plugin(config: TestConfig) -> Do:
    yield define_function(stderr_handler_name, List('id', 'data', 'event'), stderr_handler_body)
    json = yield N.from_either(dump_json(config.config))
    cmd = f'from ribosome.host import start_json_config; start_json_config({json!r})'
    args = ['python3', '-c', cmd]
    opts = dict(rpc=True, on_stderr=stderr_handler_name)
    yield nvim_call_function('jobstart', args, opts)


def cleanup(config: TestConfig) -> Do:
    @do(NvimIO[None])
    def cleanup(result: NResult) -> Do:
        yield nvim_quit()
        runtime_log = yield N.from_io(IO.delay(config.log_file.read_text))
        if runtime_log:
            log.info(green('plugin output:'))
            Lists.lines(runtime_log) % log.info
            log.info('')
    return cleanup


def plugin_test(
        config: TestConfig,
        io: Callable[..., NvimIO[Expectation]],
) -> Expectation:
    @do(NvimIO[None])
    def run_nvim_io() -> Do:
        yield config.pre()
        yield start_plugin(config)
        yield pvar_becomes('started', True)
        yield io()
    @do(IO[Expectation])
    def run() -> Do:
        nvim = yield setup_test_nvim(config)
        return N.ensure(run_nvim_io(), cleanup(config)).run_a(nvim.api)
    return k(run().attempt).must(be_right(nsuccess(match_with(lambda a: a))))


__all__ = ('TestConfig', 'TestNvim')
