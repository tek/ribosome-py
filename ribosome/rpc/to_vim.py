from concurrent.futures import Future, TimeoutError
from typing import Any, Callable, TypeVar, Union, Tuple

import msgpack

from amino import do, Do, IO, Either, List, ADT
from amino.state import IOState
from amino.lenses.lens import lens
from amino.logging import module_log
from amino.case import Case

from ribosome.rpc.error import RpcReadError
from ribosome.rpc.comm import Comm, RpcComm, RpcConcurrency, Rpc
from ribosome.nvim.io.data import NResult, NSuccess, NError, NFatal
from ribosome.rpc.concurrency import register_rpc
from ribosome.rpc.data.rpc import ActiveRpc
from ribosome.rpc.response import RpcResponse, RpcSyncError, RpcSyncSuccess

log = module_log()
A = TypeVar('A')
ResponseTuple = Union[Tuple[None, str], Tuple[Any, None]]


# FIXME loop is not part of comm, but uv
def rpc_error(comm: Comm) -> Callable[[RpcReadError], None]:
    def on_error(error: RpcReadError) -> IO[None]:
        return IO.pure(None)
        # IO.delay(comm.loop.stop)
    return on_error


def exclusive_increment(concurrency: RpcConcurrency) -> int:
    with concurrency.lock:
        concurrency.requests.current_id += 1
        return concurrency.requests.current_id


def exclusive_register_callback(concurrency: RpcConcurrency, id: int, rpc: Rpc) -> IO[Future]:
    result = Future()
    yield concurrency.exclusive(concurrency.requests.to_vim.update, {id: (result, rpc)})
    return result


def increment() -> IOState[RpcConcurrency, int]:
    return IOState.inspect(exclusive_increment)


def pack_error(metadata: list, payload: list) -> Callable[[Exception], IO[bytes]]:
    def pack_error(error: Exception) -> IO[bytes]:
        return IO.delay(msgpack.packb, metadata + [f'could not serialize response `{payload}`', None])
    return pack_error


@do(IOState[RpcComm, Any])
def send_rpc(metadata: list, payload: list) -> Do:
    send = yield IOState.inspect(lambda a: a.send)
    pack = IO.delay(msgpack.packb, metadata + payload).recover_with(pack_error(metadata, payload))
    payload = yield IOState.lift(pack)
    yield IOState.delay(send, payload)


def initiate_rpc(metadata: list, rpc: Rpc) -> IOState[RpcComm, Any]:
    log.debug1(f'initiate_rpc: {rpc}')
    return send_rpc(metadata, [rpc.method.encode(), rpc.args])


def wait_for_result(result: Future, timeout: float, rpc: Rpc) -> IO[Any]:
    try:
        r = result.result(timeout)
    except TimeoutError:
        return IO.failed(f'{rpc} timed out after {timeout}s')
    except Exception as e:
        log.caught_exception('waiting for request result future', e)
        return IO.failed(f'fatal error in {rpc}')
    else:
        return IO.from_either(r.lmap(lambda a: f'{rpc} failed: {a}'))


@do(IOState[Comm, Either[str, Any]])
def send_request(rpc: Rpc, timeout: float) -> Do:
    id = yield increment().zoom(lens.concurrency)
    active_rpc = ActiveRpc(rpc, id)
    result = yield IOState.inspect_f(lambda a: register_rpc(a, a.requests.to_vim, active_rpc)).zoom(lens.concurrency)
    yield initiate_rpc([0, id], rpc).zoom(lens.rpc)
    yield IOState.lift(wait_for_result(result, timeout, rpc))


@do(IOState[Comm, Any])
def send_notification(rpc: Rpc, timeout: float) -> Do:
    yield initiate_rpc([2], rpc).zoom(lens.rpc)


class handle_response(Case[RpcResponse, IOState[Comm, None]], alg=RpcResponse):

    @do(IOState[Comm, None])
    def error(self, response: RpcSyncError) -> Do:
        payload = [response.error, None]
        yield send_rpc([1, response.request_id], payload).zoom(lens.rpc)

    @do(IOState[Comm, None])
    def success(self, response: RpcSyncSuccess) -> Do:
        payload = [None, response.result]
        yield send_rpc([1, response.request_id], payload).zoom(lens.rpc)

    def case_default(self, response: RpcResponse) -> IOState[Comm, None]:
        return IOState.unit


__all__ = ('send_request', 'send_notification', 'handle_response',)
