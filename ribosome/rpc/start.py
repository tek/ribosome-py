from typing import Callable, TypeVar, Tuple

from amino import IO, do, Do, Nil
from amino.state import State
from amino.logging import module_log

from ribosome.rpc.comm import Comm, Rpc, RpcComm, StateGuard
from ribosome.config.config import Config
from ribosome.rpc.handle_receive import rpc_receive
from ribosome.components.internal.update import init_rpc_plugin
from ribosome.rpc.state import cons_state
from ribosome.nvim.io.compute import NvimIO, NvimIOSuspend
from ribosome.nvim.io.api import N
from ribosome.nvim.api.variable import variable_set_prefixed
from ribosome.nvim.io.state import NS
from ribosome.data.plugin_state import PS
from ribosome.logging import nvim_logging
from ribosome.rpc.to_vim import rpc_error
from ribosome.rpc.to_plugin import rpc_handler
from ribosome.rpc.from_vim import execute_rpc_from_vim
from ribosome.rpc.nvim_api import RiboNvimApi
from ribosome.components.internal.prog import internal_init
from ribosome.compute.run import run_prog

A = TypeVar('A')
log = module_log()


def start_comm(comm: Comm, execute_request: Callable[[Comm, Rpc], None]) -> IO[None]:
    return comm.rpc.start_processing(rpc_receive(comm, execute_request), rpc_error(comm))


def stop_comm(comm: Comm) -> IO[None]:
    return IO.delay(comm.rpc.stop_processing)


@do(NS[PS, None])
def init_plugin() -> Do:
    yield NS.delay(nvim_logging)
    yield init_rpc_plugin()
    yield run_prog(internal_init, Nil)
    yield NS.lift(variable_set_prefixed('started', True))


@do(IO[None])
def init_comm(rpc_comm: RpcComm, execute_request: Callable[[Comm, Rpc], IO[None]]) -> Do:
    comm = Comm.cons(rpc_handler, rpc_comm)
    yield start_comm(comm, execute_request)
    return comm


def plugin_execute_receive_request(guard: StateGuard[A], plugin_name: str) -> Callable[[Comm, Rpc], IO[None]]:
    def execute(comm: Comm, rpc: Rpc) -> IO[None]:
        return IO.fork_io(execute_rpc_from_vim, rpc, comm, comm.request_handler(guard), plugin_name)
    return execute


@do(NvimIO[Tuple[Comm, StateGuard]])
def setup_comm(config: Config, rpc_comm: RpcComm) -> Do:
    state = cons_state(config)
    guard = StateGuard.cons(state)
    execute_request = plugin_execute_receive_request(guard, config.basic.name)
    comm = yield N.from_io(init_comm(rpc_comm, execute_request))
    api = RiboNvimApi(config.basic.name, comm)
    yield NvimIOSuspend.cons(State.set(api).replace(N.pure(None)))
    return comm, guard


@do(NvimIO[None])
def start_plugin(config: Config, rpc_comm: RpcComm) -> Do:
    comm, guard = yield setup_comm(config, rpc_comm)
    state = yield init_plugin().run_s(guard.state)
    yield N.delay(lambda v: guard.init(state))
    return comm


@do(IO[None])
def start_plugin_sync(config: Config, rpc_comm: RpcComm) -> Do:
    start = start_plugin(config, rpc_comm)
    result = yield IO.delay(start.run_a, None)
    comm = yield IO.from_either(result.to_either)
    yield comm.rpc.join()


def cannot_execute_request(comm: Comm, rpc: Rpc) -> IO[None]:
    return IO.failed(f'cannot execute request in external nvim: {rpc}')


@do(IO[RiboNvimApi])
def start_external(name: str, rpc_comm: RpcComm) -> Do:
    comm = yield init_comm(rpc_comm, cannot_execute_request)
    return RiboNvimApi(name, comm)


__all__ = ('start_comm', 'stop_comm', 'init_plugin', 'init_comm', 'plugin_execute_receive_request', 'setup_comm',
           'start_plugin', 'start_plugin_sync', 'cannot_execute_request', 'start_external',)
