from concurrent.futures import Future
from typing import Any, Callable, TypeVar, Generic, Optional
from threading import Lock

from amino import Dat, Map, List, Either, IO, ADT, do, Do, Try
from amino.logging import module_log

from ribosome.rpc.error import RpcReadError
from ribosome.nvim.io.api import N
from ribosome.nvim.io.state import NS
from ribosome.nvim.io.compute import NvimIO, lift_n_result
from ribosome.nvim.io.data import NResult

A = TypeVar('A')
B = TypeVar('B')
log = module_log()


class RpcType(ADT['RpcType']):
    pass


class BlockingRpc(RpcType):

    def __init__(self, id: int) -> None:
        self.id = id


class NonblockingRpc(RpcType):
    pass


class Rpc(Dat['Rpc']):

    @staticmethod
    def nonblocking(method: str, args: List[Any]) -> 'Rpc':
        return Rpc(method, args, NonblockingRpc())

    def __init__(self, method: str, args: List[Any], tpe: RpcType) -> None:
        self.method = method
        self.args = args
        self.tpe = tpe

    @property
    def sync(self) -> bool:
        return isinstance(self.tpe, BlockingRpc)


Exec = Callable[[Rpc], Either[str, Any]]


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


# FIXME send/exit should be IO
class RpcComm(Dat['RpcComm']):

    def __init__(
            self,
            start_processing: Callable[[OnMessage, OnError], IO[None]],
            stop_processing: Callable[[], IO[None]],
            send: Callable[[bytes], None],
            join: Callable[[], IO[None]],
            exit: Callable[[], None],
    ) -> None:
        self.start_processing = start_processing
        self.stop_processing = stop_processing
        self.join = join
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
            request_handler: Exec,
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


class StateGuard(Generic[A], Dat['StateGuard']):

    @staticmethod
    def cons(state: A) -> 'StateGuard[A]':
        return StateGuard(state, Lock())

    def __init__(self, state: A, lock: Lock) -> None:
        self.state = state
        self.lock = lock

    def exclusive(self, f: Callable[..., A], *a: Any, **kw: Any) -> Any:
        with self.lock:
            return f(*a, **kw)

    def exclusive_state(self, f: Callable[..., A], *a: Any, **kw: Any) -> None:
        with self.lock:
            self.state = f(self.state, *a, **kw)

    def update(self, state: A) -> None:
        self.exclusive(setattr, self, 'state', state)

    @do(NvimIO[None])
    def acquire(self) -> Do:
        yield N.simple(self.lock.acquire)

    @do(NvimIO[None])
    def release(self, result: Optional[NResult[A]]=None) -> Do:
        yield N.simple(Try, self.lock.release)
        if result:
            log.debug(f'released lock due to error: {result}')
            yield lift_n_result.match(result)


@do(NvimIO[B])
def exclusive_ns(guard: StateGuard[A], desc: str, thunk: Callable[..., NS[A, B]], *a: Any) -> Do:
    '''this is the central unsafe function, using a lock and updating the state in `guard` in-place.
    '''
    yield guard.acquire()
    log.debug2(lambda: f'exclusive: {desc}')
    state, response = yield N.ensure_failure(thunk(*a).run(guard.state), guard.release)
    yield N.delay(lambda v: guard.update(state))
    yield guard.release()
    log.debug2(lambda: f'release: {desc}')
    yield N.pure(response)


__all__ = ('Comm', 'Rpc', 'Requests', 'OnMessage', 'OnError', 'RpcComm', 'RpcConcurrency', 'StateGuard')
