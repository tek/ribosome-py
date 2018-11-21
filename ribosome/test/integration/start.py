from amino import do, Do
from amino.json import dump_json

from ribosome.nvim.io.compute import NvimIO
from ribosome.test.config import TestConfig
from ribosome.nvim.api.function import nvim_call_function
from ribosome.config.config import Config
from ribosome.nvim.io.api import N
from ribosome.rpc.error import define_rpc_stderr_handler

stderr_handler_prefix = 'RibosomeSpec'


def start_plugin_cmd_import(path: str) -> NvimIO[str]:
    return N.pure(f'from ribosome.host import start_path; start_path({path!r})')


@do(NvimIO[str])
def start_plugin_cmd_json(config: Config) -> Do:
    json = yield N.from_either(dump_json(config))
    return f'from ribosome.host import start_json_config; start_json_config({json!r})'


@do(NvimIO[None])
def start_plugin_embed(config: TestConfig) -> Do:
    stderr_handler_name = yield define_rpc_stderr_handler(stderr_handler_prefix)
    cmd = yield (
        config.config_path.cata(
            start_plugin_cmd_import,
            lambda: start_plugin_cmd_json(config.config),
        )
    )
    args = ['python3', '-c', cmd]
    opts = dict(rpc=True, on_stderr=stderr_handler_name)
    yield nvim_call_function('jobstart', args, opts)


__all__ = ('start_plugin_embed',)
