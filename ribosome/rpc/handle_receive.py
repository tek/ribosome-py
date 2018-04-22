from concurrent.futures import Future
from typing import Callable, Tuple, Any

import msgpack

from amino import do, Do, Try, IO, List
from amino.case import Case
from amino.logging import module_log

from ribosome.rpc.receive import (cons_receive, ReceiveResponse, ReceiveError, Receive, ReceiveRequest,
                                  ReceiveNotification, ReceiveExit, ReceiveUnknown)
from ribosome.data.plugin_state_holder import PluginStateHolder
from ribosome.rpc.comm import Comm, Requests, RpcConcurrency, Rpc
from ribosome.rpc.execute_request import execute_request

log = module_log()


@do(IO[Future])
def prepare_request(requests: Requests, id: int) -> Do:
    f = Future()
    yield IO.delay(requests.from_vim.update, id=f)
    return f


def resolve_rpc(requests: Requests, id: int) -> IO[Tuple[Future, Rpc]]:
    return IO.delay(requests.to_vim.pop, id)


@do(IO[None])
def notify(requests: Requests, data: ReceiveResponse) -> Do:
    fut, rpc = yield resolve_rpc(requests, data.id)
    yield IO.delay(fut.set_result, data.data)


@do(IO[None])
def notify_error(requests: Requests, err: ReceiveError) -> Do:
    print(f'notify_error: {err}')
    fut, rpc = yield resolve_rpc(requests, err.id)
    yield IO.delay(fut.cancel)
    yield IO.failed(f'{rpc} failed: {err.error}')


@do(IO[Any])
def execute_receive_request(
        comm: Comm,
        id: int,
        method: str,
        args: List[Any],
        sync: bool,
        holder: PluginStateHolder,
) -> Do:
    yield comm.concurrency.exclusive(prepare_request, comm.concurrency.requests, id)
    yield IO.delay(
        execute_request,
        comm,
        id,
        method,
        args,
        True,
        comm.request_handler(holder)
    )



class handle_receive(Case[Receive, IO[None]], alg=Receive):

    def __init__(self, comm: Comm, holder: PluginStateHolder) -> None:
        self.comm = comm
        self.holder = holder

    @property
    def concurrency(self) -> RpcConcurrency:
        return self.comm.concurrency

    @property
    def requests(self) -> Requests:
        return self.concurrency.requests

    def response(self, data: ReceiveResponse) -> IO[None]:
        return self.concurrency.exclusive(notify, self.requests, data)

    def error(self, err: ReceiveError) -> IO[None]:
        return self.concurrency.exclusive(notify_error, self.requests, err)

    def request(self, receive: ReceiveRequest) -> IO[None]:
        return execute_receive_request(self.comm, receive.id, receive.method, receive.args, True, self.holder)

    def notification(self, receive: ReceiveNotification) -> IO[None]:
        return execute_receive_request(self.comm, receive.id, receive.method, receive.args, False, self.holder)

    def exit(self, receive: ReceiveExit) -> IO[None]:
        return IO.pure(None)

    def unknown(self, receive: ReceiveUnknown) -> IO[None]:
        return IO.delay(log.error, f'received unknown rpc: {receive}')


def rpc_receive(comm: Comm, holder: PluginStateHolder) -> Callable[[bytes], IO[None]]:
    @do(IO[None])
    def on_read(blob: bytes) -> Do:
        data = yield IO.delay(msgpack.unpackb, blob).recover_with(lambda e: IO.failed(f'failed to unpack: {e}'))
        receive = cons_receive(data)
        yield handle_receive(comm, holder)(receive)
    return on_read


__all__ = ('rpc_receive',)
