from concurrent.futures import Future
from typing import Callable, Tuple, Generic, TypeVar, Any

import msgpack

from amino import do, Do, IO, Right, Left, List, Lists
from amino.case import Case
from amino.logging import module_log

from ribosome.rpc.receive import (cons_receive, ReceiveResponse, ReceiveError, Receive, ReceiveRequest,
                                  ReceiveNotification, ReceiveExit, ReceiveUnknown)
from ribosome.rpc.comm import Comm
from ribosome.rpc.concurrency import Requests, RpcConcurrency
from ribosome.rpc.data.rpc import Rpc
from ribosome.rpc.data.rpc_type import BlockingRpc

log = module_log()
A = TypeVar('A')


def resolve_rpc(requests: Requests, id: int) -> IO[Tuple[Future, Rpc]]:
    return IO.delay(requests.to_vim.pop, id)


@do(IO[None])
def publish_response_from_vim(requests: Requests, data: ReceiveResponse) -> Do:
    fut = yield resolve_rpc(requests, data.id)
    yield IO.delay(fut.set_result, Right(data.data))


@do(IO[None])
def publish_error_from_vim(requests: Requests, err: ReceiveError) -> Do:
    fut = yield resolve_rpc(requests, err.id)
    yield IO.delay(fut.set_result, Left(err.error))


class handle_receive(Generic[A], Case[Receive, IO[None]], alg=Receive):

    def __init__(self, comm: Comm, execute_plugin_rpc: Callable[[Comm, Rpc], IO[None]]) -> None:
        self.comm = comm
        self.execute_plugin_rpc = execute_plugin_rpc

    @property
    def concurrency(self) -> RpcConcurrency:
        return self.comm.concurrency

    @property
    def requests(self) -> Requests:
        return self.concurrency.requests

    def response(self, data: ReceiveResponse) -> IO[None]:
        return self.concurrency.exclusive(publish_response_from_vim, self.requests, data)

    def error(self, err: ReceiveError) -> IO[None]:
        return self.concurrency.exclusive(publish_error_from_vim, self.requests, err)

    def request(self, receive: ReceiveRequest) -> IO[None]:
        return self.execute_plugin_rpc(self.comm, Rpc(receive.method, receive.args, BlockingRpc(receive.id)))

    def notification(self, receive: ReceiveNotification) -> IO[None]:
        return self.execute_plugin_rpc(self.comm, Rpc.nonblocking(receive.method, receive.args))

    def exit(self, receive: ReceiveExit) -> IO[None]:
        log.debug('exiting rpc session')
        return IO.pure(None)

    def unknown(self, receive: ReceiveUnknown) -> IO[None]:
        return IO.delay(log.error, f'received unknown rpc: {receive}')


@do(IO[List[Any]])
def unpack(data: bytes) -> Do:
    unpacker = msgpack.Unpacker()
    yield IO.delay(unpacker.feed, data)
    raw = yield IO.delay(list, unpacker)
    return Lists.wrap(raw)


def rpc_receive(comm: Comm, execute_plugin_rpc: Callable[[Comm, Rpc], None]) -> Callable[[bytes], IO[None]]:
    def handle(data: Any) -> IO[None]:
        receive = cons_receive(data)
        return handle_receive(comm, execute_plugin_rpc)(receive)
    @do(IO[None])
    def on_read(blob: bytes) -> Do:
        data = yield IO.delay(unpack, blob).recover_with(lambda e: IO.failed(f'failed to unpack: {e}'))
        yield data.traverse(handle, IO)
        yield IO.pure(None)
    return on_read


__all__ = ('rpc_receive',)
