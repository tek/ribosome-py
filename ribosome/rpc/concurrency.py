from concurrent.futures import Future
from typing import Any, Callable, TypeVar
from threading import Lock

from amino import do, Do, IO, Map, Dat
from amino.logging import module_log

from ribosome.rpc.error import RpcReadError
from ribosome.rpc.data.rpc import ActiveRpc

A = TypeVar('A')
log = module_log()


PendingRpc = Map[int, Future]


class Requests(Dat['Requests']):

    @staticmethod
    def cons(current_id: int=0, to_vim: PendingRpc=Map(), from_vim: PendingRpc=Map()) -> 'Requests':
        return Requests(current_id, to_vim, from_vim)

    def __init__(self, current_id: int, to_vim: PendingRpc, from_vim: PendingRpc) -> None:
        self.current_id = current_id
        self.to_vim = to_vim
        self.from_vim = from_vim


OnMessage = Callable[[bytes], IO[None]]
OnError = Callable[[RpcReadError], IO[None]]


class RpcConcurrency(Dat['RpcConcurrency']):

    @staticmethod
    def cons(
            requests: Requests=None,
            lock: Lock=None,
    ) -> 'RpcConcurrency':
        return RpcConcurrency(
            requests or Requests.cons(),
            lock or Lock(),
        )

    def exclusive(self, f: Callable[..., IO[A]], *a: Any, **kw: Any) -> IO[A]:
        def wrap() -> IO[A]:
            with self.lock:
                return IO.from_either(f(*a, **kw).attempt)
        return IO.suspend(wrap)

    def __init__(self, requests: Requests, lock: Lock) -> None:
        self.requests = requests
        self.lock = lock


def exclusive_unregister_rpc(rc: RpcConcurrency, requests: PendingRpc, rpc: ActiveRpc) -> IO[Future]:
    return IO.delay(requests.pop, rpc.id)


def unregister_rpc(rc: RpcConcurrency, requests: PendingRpc, rpc: ActiveRpc) -> IO[Future]:
    log.debug1(f'unregistering {rpc}')
    return (
        IO.failed(f'invalid request id from vim after execution: {rpc}. active requests: {requests}')
        if rpc.id not in requests else
        rc.exclusive(exclusive_unregister_rpc, rc, requests, rpc)
    )


@do(IO[Future])
def exclusive_register_rpc(rc: RpcConcurrency, requests: PendingRpc, rpc: ActiveRpc) -> Do:
    f: Future = Future()
    yield IO.delay(requests.update, {rpc.id: f})
    return f


@do(IO[Future])
def register_rpc(rc: RpcConcurrency, requests: PendingRpc, rpc: ActiveRpc) -> Do:
    log.debug1(f'registering {rpc}')
    yield (
        IO.failed(f'duplicate id in request from vim: {rpc}')
        if rpc.id in requests else
        rc.exclusive(exclusive_register_rpc, rc, requests, rpc)
    )

__all__ = ('Requests', 'OnMessage', 'OnError', 'RpcConcurrency', 'unregister_rpc', 'register_rpc',)
