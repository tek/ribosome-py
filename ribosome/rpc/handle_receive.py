from concurrent.futures import Future
from typing import Callable, Tuple, Generic, TypeVar

import msgpack

from amino import do, Do, IO
from amino.case import Case
from amino.logging import module_log

from ribosome.rpc.receive import (cons_receive, ReceiveResponse, ReceiveError, Receive, ReceiveRequest,
                                  ReceiveNotification, ReceiveExit, ReceiveUnknown)
from ribosome.rpc.comm import Comm, Requests, RpcConcurrency, Rpc, BlockingRpc
from ribosome import ribo_log

log = module_log()
A = TypeVar('A')


def resolve_rpc(requests: Requests, id: int) -> IO[Tuple[Future, Rpc]]:
    return IO.delay(requests.to_vim.pop, id)


@do(IO[None])
def notify(requests: Requests, data: ReceiveResponse) -> Do:
    fut, rpc = yield resolve_rpc(requests, data.id)
    yield IO.delay(fut.set_result, data.data)


@do(IO[None])
def notify_error(requests: Requests, err: ReceiveError) -> Do:
    log.debug(f'notify_error: {err}')
    fut, rpc = yield resolve_rpc(requests, err.id)
    log.debug(f'{rpc} failed: {err.error}')
    yield IO.delay(fut.cancel)


class handle_receive(Generic[A], Case[Receive, IO[None]], alg=Receive):

    def __init__(self, comm: Comm, execute_rpc: Callable[[Comm, Rpc], None]) -> None:
        self.comm = comm
        self.execute_rpc = execute_rpc

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
        return self.execute_rpc(self.comm, Rpc(receive.method, receive.args, BlockingRpc(receive.id)))

    def notification(self, receive: ReceiveNotification) -> IO[None]:
        return self.execute_rpc(self.comm, Rpc.nonblocking(receive.method, receive.args))

    def exit(self, receive: ReceiveExit) -> IO[None]:
        log.debug('exiting rpc session')
        return IO.pure(None)

    def unknown(self, receive: ReceiveUnknown) -> IO[None]:
        return IO.delay(log.error, f'received unknown rpc: {receive}')


def rpc_receive(comm: Comm, execute_rpc: Callable[[Comm, Rpc], None]) -> Callable[[bytes], IO[None]]:
    @do(IO[None])
    def on_read(blob: bytes) -> Do:
        data = yield IO.delay(msgpack.unpackb, blob).recover_with(lambda e: IO.failed(f'failed to unpack: {e}'))
        receive = cons_receive(data)
        yield handle_receive(comm, execute_rpc)(receive)
    return on_read


__all__ = ('rpc_receive',)
