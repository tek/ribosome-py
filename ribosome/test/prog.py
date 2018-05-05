from typing import Any, Callable

from amino import List, do, Do, Just

from ribosome.rpc.api import RpcProgram
from ribosome.nvim.io.state import NS
from ribosome.data.plugin_state import PS
from ribosome.rpc.to_plugin import run_program
from ribosome.rpc.data.rpc import RpcArgs
from ribosome.test.config import TestConfig
from ribosome.rpc.state import cons_state
from ribosome.nvim.io.api import N
from ribosome.logging import nvim_logging
from ribosome.nvim.io.compute import NvimIO
from ribosome.components.internal.update import update_components


def program_runner(args: List[Any]) -> Callable[[RpcProgram], NS[PS, Any]]:
    def runner(program: RpcProgram) -> NS[PS, Any]:
        return run_program(program, RpcArgs.cons(args))
    return runner


@do(NS[PS, Any])
def request(method: str, args: List[Any]) -> Do:
    progs = yield NS.inspect(lambda a: a.programs)
    matches = progs.filter(lambda a: a.program.name == method)
    yield matches.traverse(program_runner(args), NS)


@do(NvimIO[PS])
def init_test_state(config: TestConfig) -> Do:
    log_handler = yield N.delay(nvim_logging)
    state = cons_state(config.config, config.io_interpreter, config.logger, log_handler=log_handler)
    yield update_components(Just(config.components)).nvim.run_s(state)


__all__ = ('program_runner', 'request', 'init_test_state',)
