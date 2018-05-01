from typing import Callable, TypeVar, Tuple

from amino import IO, do, Do
from amino.state import State
from amino.logging import module_log

from ribosome.rpc.comm import Comm, Rpc, RpcComm, StateGuard
from ribosome.config.config import Config
from ribosome.rpc.handle_receive import rpc_receive
from ribosome.rpc.handle import rpc_error, comm_request_handler
from ribosome.components.internal.update import init_rpc_plugin
from ribosome.rpc.api import RiboNvimApi
from ribosome.rpc.state import cons_state
from ribosome.nvim.io.compute import NvimIO, NvimIOSuspend
from ribosome.nvim.io.api import N
from ribosome.nvim.api.variable import variable_set_prefixed
from ribosome.nvim.io.state import NS
from ribosome.data.plugin_state import PS
from ribosome.rpc.execute import execute_rpc
from ribosome import ribo_log
from ribosome.logging import nvim_logging

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
    # yield N.from_io(IO.delay(session._enqueue_notification, 'function:internal_init', ()))
    yield NS.lift(variable_set_prefixed('started', True))


@do(IO[None])
def init_comm(rpc_comm: RpcComm, execute_request: Callable[[Comm, Rpc], IO[None]]) -> Do:
    comm = Comm.cons(comm_request_handler, rpc_comm)
    yield start_comm(comm, execute_request)
    return comm


def plugin_execute_receive_request(guard: StateGuard[A]) -> Callable[[Comm, Rpc], IO[None]]:
    def execute(comm: Comm, rpc: Rpc) -> IO[None]:
        return execute_rpc(rpc, comm, comm.request_handler(guard))(rpc.tpe)
    return execute


@do(NvimIO[Tuple[Comm, StateGuard]])
def setup_comm(config: Config, rpc_comm: RpcComm) -> Do:
    state = cons_state(config)
    guard = StateGuard.cons(state)
    execute_request = plugin_execute_receive_request(guard)
    comm = yield N.from_io(init_comm(rpc_comm, execute_request))
    api = RiboNvimApi(config.basic.name, comm)
    yield NvimIOSuspend.cons(State.set(api).replace(N.pure(None)))
    return comm, guard


@do(NvimIO[None])
def start_plugin(config: Config, rpc_comm: RpcComm) -> Do:
    comm, guard = yield setup_comm(config, rpc_comm)
    state = yield init_plugin().run_s(guard.state)
    yield N.delay(lambda v: guard.update(state))
    return comm


@do(IO[None])
def start_plugin_sync(config: Config, rpc_comm: RpcComm) -> Do:
    start = start_plugin(config, rpc_comm)
    result = yield IO.delay(start.run_a, None)
    comm = yield IO.from_either(result.to_either)
    yield comm.rpc.join()


def start_embed() -> None:
    pass


def cannnot_execute_request(comm: Comm, rpc: Rpc, sync: bool) -> IO[None]:
    return IO.failed(f'cannot execute request in external nvim')


@do(IO[RiboNvimApi])
def start_external(name: str, rpc_comm: RpcComm) -> Do:
    comm = yield init_comm(rpc_comm, cannnot_execute_request)
    return RiboNvimApi(name, comm)


__all__ = ('start_comm', 'stop_comm')
