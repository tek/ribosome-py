from concurrent.futures import Future
from typing import Any, Callable, TypeVar
from threading import Lock

from amino import Dat, Map, List, Either, IO

from ribosome.rpc.error import RpcReadError

A = TypeVar('A')


class Rpc(Dat['Rpc']):

    def __init__(self, method: str, args: List[Any]) -> None:
        self.method = method
        self.args = args


class Requests(Dat['Requests']):

    @staticmethod
    def cons(current_id: int=0, to_vim: Map[int, Future]=Map(), from_vim: Map[int, Future]=Map()) -> 'Requests':
        return Requests(current_id, to_vim, from_vim)

    def __init__(self, current_id: int, to_vim: Map[int, Future], from_vim: Map[int, Future]) -> None:
        self.current_id = current_id
        self.to_vim = to_vim
        self.from_vim = from_vim


OnMessage = Callable[[bytes], IO[None]]
OnError = Callable[[RpcReadError], IO[None]]


class RpcComm(Dat['RpcComm']):

    def __init__(
            self,
            start_processing: Callable[[OnMessage, OnError], IO[None]],
            send: Callable[[bytes], None],
            exit: Callable[[], None],
    ) -> None:
        self.start_processing = start_processing
        self.send = send
        self.exit = exit


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


class Comm(Dat['Comm']):

    @staticmethod
    def cons(
            request_handler: Callable[[str, List[Any], bool], Either[str, Any]],
            rpc: RpcComm,
            concurrency: RpcConcurrency=None,
    ) -> 'Comm':
        return Comm(request_handler, rpc, concurrency or RpcConcurrency.cons())

    def __init__(
            self,
            request_handler: Callable[[str, List[Any], bool], Either[str, Any]],
            rpc: RpcComm,
            concurrency: RpcConcurrency,
    ) -> None:
        self.request_handler = request_handler
        self.rpc = rpc
        self.concurrency = concurrency

    @property
    def lock(self) -> Lock:
        return self.concurrency.lock


__all__ = ('Comm', 'Rpc', 'Requests', 'OnMessage', 'OnError', 'RpcComm', 'RpcConcurrency')
