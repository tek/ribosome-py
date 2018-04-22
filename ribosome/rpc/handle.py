from concurrent.futures import Future
from typing import Any, Callable

import msgpack

from amino import List, do, Do, Try, _, IO
from amino.state import EitherState
from amino.lenses.lens import lens
from amino.logging import module_log

from ribosome.rpc.error import RpcReadError
from ribosome.data.plugin_state_holder import PluginStateHolder
from ribosome.nvim.io.compute import NvimIO
from ribosome.request.execute import execute_request_io
from ribosome.rpc.comm import Comm, RpcComm, RpcConcurrency, Rpc

log = module_log()


# FIXME loop is not part of comm, but uv
# add `stop` handler to `RpcComm`?
def rpc_error(comm: Comm) -> Callable[[RpcReadError], None]:
    def on_error(error: RpcReadError) -> IO[None]:
        return IO.pure(None)
        # IO.delay(comm.loop.stop)
    return on_error


def exclusive_increment(concurrency: RpcConcurrency) -> None:
    with concurrency.lock:
        concurrency.requests.current_id += 1


def exclusive_register_callback(comm: Comm, id: int, rpc: Rpc) -> Future:
    result = Future()
    with comm.lock:
        comm.requests.to_vim[id] = (result, rpc)
    return result


@do(EitherState[RpcConcurrency, int])
def increment() -> Do:
    yield EitherState.inspect(exclusive_increment)
    yield EitherState.inspect(_.requests.current_id)


@do(EitherState[RpcComm, Any])
def send_rpc(metadata: list, rpc: Rpc) -> Do:
    send = yield EitherState.inspect(lambda a: a.send)
    payload = yield EitherState.lift(Try(msgpack.packb, metadata + [rpc.method.encode(), rpc.args]))
    yield EitherState.lift(Try(send, payload))


@do(EitherState[Comm, Any])
def send_request(rpc: Rpc, timeout: float) -> Do:
    id = yield increment().zoom(lens.concurrency)
    result = yield EitherState.inspect(lambda a: exclusive_register_callback(a.concurrency, id, rpc))
    yield send_rpc([0, id], rpc).zoom(lens.rpc)
    yield EitherState.lift(Try(result.result, timeout).lmap(lambda a: f'{rpc} timed out after {timeout}s'))


@do(EitherState[Comm, Any])
def send_notification(rpc: Rpc, timeout: float) -> Do:
    yield send_rpc([2], rpc).zoom(lens.rpc)


# TODO `request_result` is not called with `execute_request_io`
def comm_request_handler(holder: PluginStateHolder) -> Callable[[str, List[Any], bool], NvimIO[Any]]:
    def handler(method: str, args: List[Any], sync: bool) -> NvimIO[Any]:
        return execute_request_io(holder, method, args, sync)
    return handler


__all__ = ()
