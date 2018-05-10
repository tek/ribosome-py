from typing import Callable, Any

from kallikrein import Expectation

from amino import do, Do, IO, List, Lists
from amino.json import dump_json
from amino.logging import module_log
from amino.string.hues import green

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.io.api import N
from ribosome.nvim.api.function import define_function, nvim_call_function
from ribosome.nvim.api.rpc import nvim_quit
from ribosome.nvim.api.variable import pvar_becomes
from ribosome.nvim.io.data import NResult
from ribosome.test.config import TestConfig
from ribosome.test.integration.rpc import setup_test_nvim_embed, set_nvim_vars
from ribosome.test.run import run_test_io

log = module_log()
stderr_handler_name = 'RibosomeSpecStderr'
stderr_handler_body = '''
let err = substitute(join(a:data, '\\r'), '"', '\\"', 'g')
python3 import amino
python3 from ribosome.logging import ribosome_envvar_file_logging
python3 ribosome_envvar_file_logging()
execute 'python3 amino.amino_log.error(f"""error starting rpc job on channel ' . a:id . ':\\r' . err . '""")'
'''


@do(NvimIO[None])
def start_plugin_embed(config: TestConfig) -> Do:
    yield define_function(stderr_handler_name, List('id', 'data', 'event'), stderr_handler_body)
    json = yield N.from_either(dump_json(config.config))
    cmd = f'from ribosome.host import start_json_config; start_json_config({json!r})'
    args = ['python3', '-c', cmd]
    opts = dict(rpc=True, on_stderr=stderr_handler_name)
    yield nvim_call_function('jobstart', args, opts)


def cleanup(config: TestConfig) -> Callable[[NResult], NvimIO[None]]:
    @do(NvimIO[None])
    def cleanup(result: NResult) -> Do:
        yield nvim_quit()
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
        yield start_plugin_embed(config)
        yield pvar_becomes('started', True)
        yield io(*a, **kw)
    @do(IO[Expectation])
    def run() -> Do:
        nvim = yield setup_test_nvim_embed(config)
        yield N.to_io_a(N.ensure(run_nvim_io(), cleanup(config)), nvim.api)
    return run_test_io(run)


__all__ = ('plugin_test',)
