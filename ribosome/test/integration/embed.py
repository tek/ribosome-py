from typing import Callable

from kallikrein import Expectation, k
from kallikrein.matchers.match_with import match_with
from kallikrein.matchers.either import be_right

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
from ribosome.test.klk.matchers.nresult import nsuccess
from ribosome.test.config import TestConfig
from ribosome.test.integration.rpc import setup_test_nvim


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
def start_plugin(config: TestConfig) -> Do:
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
