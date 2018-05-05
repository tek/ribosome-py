from concurrent.futures import Future, TimeoutError
from typing import Any, Callable, TypeVar

import msgpack

from amino import do, Do, Try, IO, Either, Left, List
from amino.state import IOState
from amino.lenses.lens import lens
from amino.logging import module_log
from amino.case import Case

from ribosome.rpc.error import RpcReadError
from ribosome.rpc.comm import Comm, RpcComm, RpcConcurrency, Rpc
from ribosome.nvim.io.data import NResult, NSuccess, NError, NFatal
from ribosome.rpc.concurrency import register_rpc
from ribosome.rpc.data.rpc import ActiveRpc

log = module_log()
A = TypeVar('A')


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


@do(IOState[RpcComm, Any])
def send_rpc(metadata: list, payload: list) -> Do:
    send = yield IOState.inspect(lambda a: a.send)
    payload = yield IOState.delay(msgpack.packb, metadata + payload)
    yield IOState.delay(send, payload)


def initiate_rpc(metadata: list, rpc: Rpc) -> IOState[RpcComm, Any]:
    log.debug(f'initiate_rpc: {rpc}')
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


def success_result(result: Any) -> List[Any]:
    return [None, result]


def error_result(message: str) -> List[Any]:
    return [message, None]


def ensure_single_result(rpc: Rpc) -> List[Any]:
    def ensure_single_result(head: Any, tail: List[Any]) -> List[Any]:
        return (
            success_result(head)
            if tail.empty else
            error_result(f'multiple results for {rpc}')
        )
    return ensure_single_result


def no_result(rpc: Rpc) -> List[Any]:
    return error_result(f'no result for {rpc}')


class response_payload_to_vim(Case[NResult, List[Any]], alg=NResult):

    def __init__(self, rpc: Rpc) -> None:
        self.rpc = rpc

    def success(self, result: NSuccess[List[Any]]) -> List[Any]:
        return result.value.uncons.map2(ensure_single_result(self.rpc)).get_or(no_result, self.rpc)

    def error(self, result: NError[List[Any]]) -> List[Any]:
        return error_result(result.error)

    def fatal(self, result: NFatal[List[Any]]) -> List[Any]:
        log.caught_exception_error(f'executing {self.rpc} from vim', result.exception)
        return error_result('fatal error in {rpc}')


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


@do(IOState[Comm, None])
def send_response(rpc: Rpc, id: int, result: NResult[List[Any]]) -> Do:
    payload = response_payload_to_vim(rpc)(result)
    yield send_rpc([1, id], payload).zoom(lens.rpc)


__all__ = ('send_request', 'send_notification',)
