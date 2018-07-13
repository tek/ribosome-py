from typing import Any, Callable, TypeVar, Generic, Optional
from threading import Lock

from amino import Dat, List, Either, IO, do, Do, Try
from amino.logging import module_log

from ribosome.nvim.io.api import N
from ribosome.nvim.io.state import NS
from ribosome.nvim.io.compute import NvimIO, lift_n_result
from ribosome.nvim.io.data import NResult
from ribosome.rpc.concurrency import RpcConcurrency, OnMessage, OnError
from ribosome.rpc.data.rpc import Rpc

A = TypeVar('A')
B = TypeVar('B')
log = module_log()
Exec = Callable[[str, List[Any]], NvimIO[List[Any]]]


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
        self.send = send
        self.join = join
        self.exit = exit


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
    def cons(state: A, initialized: bool=False) -> 'StateGuard[A]':
        return StateGuard(state, initialized, Lock())

    def __init__(self, state: A, initialized: bool, lock: Lock) -> None:
        self.state = state
        self.initialized = initialized
        self.lock = lock

    def exclusive(self, f: Callable[..., A], *a: Any, **kw: Any) -> Any:
        with self.lock:
            return f(*a, **kw)

    def exclusive_state(self, f: Callable[..., A], *a: Any, **kw: Any) -> None:
        with self.lock:
            self.state = f(self.state, *a, **kw)

    def update(self, state: A) -> None:
        self.exclusive(setattr, self, 'state', state)

    def init(self, state: A) -> None:
        self.update(state)
        self.exclusive(setattr, self, 'initialized', True)

    @do(NvimIO[None])
    def acquire(self) -> Do:
        yield N.simple(self.lock.acquire)

    @do(NvimIO[None])
    def release(self, result: Optional[NResult[A]]=None) -> Do:
        yield N.simple(Try, self.lock.release)
        if result:
            log.debug(f'released lock due to error: {result}')
            yield lift_n_result.match(result)


def unsafe_update_state(guard: StateGuard[A], state: A) -> None:
    guard.state = state


@do(NvimIO[B])
def exclusive_ns(guard: StateGuard[A], desc: str, thunk: Callable[..., NS[A, B]], *a: Any) -> Do:
    '''this is the central unsafe function, using a lock and updating the state in `guard` in-place.
    '''
    yield guard.acquire()
    log.debug2(lambda: f'exclusive: {desc}')
    state, response = yield N.ensure_failure(thunk(*a).run(guard.state), guard.release)
    yield N.delay(lambda v: unsafe_update_state(guard, state))
    yield guard.release()
    log.debug2(lambda: f'release: {desc}')
    yield N.pure(response)


__all__ = ('Comm', 'OnError', 'RpcComm', 'StateGuard')
