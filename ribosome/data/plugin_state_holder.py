import abc
import queue
import logging
from typing import TypeVar, Generic, Optional
from threading import Lock

import greenlet

from amino import Boolean, Maybe, Nothing, Try, do, Do, IO, Dat

from ribosome.nvim.io.compute import NvimIO, lift_n_result
from ribosome.logging import Logging
from ribosome.nvim.io.api import N
from ribosome.nvim.io.data import NResult
from ribosome.data.plugin_state import PluginState
from ribosome.config.settings import Settings

A = TypeVar('A')
CC = TypeVar('CC')
D = TypeVar('D')
S = TypeVar('S', bound=Settings)


class PluginStateHolder(Generic[D], Dat['PluginStateHolder[D]'], Logging):

    @staticmethod
    def concurrent(state: PluginState[S, D, CC], log_handler: logging.Handler=None) -> 'PluginStateHolder[D]':
        return ConcurrentPluginStateHolder(state, Maybe.check(log_handler), Lock(), False)

    @staticmethod
    def strict(state: PluginState[S, D, CC], log_handler: logging.Handler=None) -> 'PluginStateHolder[D]':
        return StrictPluginStateHolder(state, log_handler)

    def __init__(self, state: PluginState[S, D, CC], log_handler: Maybe[logging.Handler]=Nothing) -> None:
        self.state = state
        self.log_handler = log_handler

    def update(self, state: PluginState[S, D, CC]) -> None:
        self.state = state

    @abc.abstractmethod
    def acquire(self) -> NvimIO[None]:
        ...

    @abc.abstractmethod
    def release(self, result: Optional[NResult[A]]=None) -> NvimIO[None]:
        ...

    @abc.abstractmethod
    def request_complete(self) -> IO[None]:
        ...


class ConcurrentPluginStateHolder(Generic[D], PluginStateHolder[D]):

    def __init__(
            self,
            state: PluginState[S, D, CC],
            log_handler: Maybe[logging.Handler],
            lock: Lock,
            running: Boolean,
    ) -> None:
        super().__init__(state, log_handler)
        self.lock = lock
        self.running = running
        self.waiting_greenlets = queue.Queue()

    def _enqueue_greenlet(self) -> None:
        self.waiting_greenlets.put(greenlet.getcurrent())

    def _pop_greenlet(self, error: Exception=None) -> None:
        if error:
            self.log.caught_exception(f'switching to parent greenlet in `acquire`', error)
        gr = self.waiting_greenlets.get()
        self.waiting_greenlets.task_done()
        return gr

    @do(NvimIO[None])
    def acquire(self) -> Do:
        '''acquire the state lock that prevents multiple programs from updating the state asynchronously.
        If the lock is already acquired, an async request is currently executing while another (sync or async) has been
        requested. In order not to block on requests to vim from the running request, the greenlet that was started by
        the vim session must be suspended, giving control back to the running async request at the point where the vim
        request was made.
        '''
        def switch() -> None:
            self.log.debug(f'acquire: switching to running request')
            self._enqueue_greenlet()
            Try(lambda: greenlet.getcurrent().parent.switch()).leffect(self._pop_greenlet)
        if self.running:
            yield N.simple(switch)
        yield N.simple(self.lock.acquire)
        yield N.simple(setattr, self, 'running', True)

    @do(NvimIO[None])
    def release(self, result: Optional[NResult[A]]=None) -> Do:
        yield N.simple(setattr, self, 'running', False)
        yield N.simple(Try, self.lock.release)
        if result:
            self.log.debug(f'released lock due to error: {result}')
            yield lift_n_result.match(result)

    @do(IO[None])
    def request_complete(self) -> Do:
        '''switch back to the request that was suspended in `acquire` while the request executing this method was
        running.
        '''
        if not self.waiting_greenlets.empty():
            self.log.debug('release: switching to waiting request')
            gr = yield IO.delay(self._pop_greenlet)
            yield IO.delay(gr.switch)
        yield IO.pure(None)


class StrictPluginStateHolder(Generic[D], PluginStateHolder[D]):
    pass

    def acquire(self) -> NvimIO[None]:
        return N.pure(None)

    def release(self, result: Optional[NResult[A]]=None) -> NvimIO[None]:
        return N.pure(None)

    def request_complete(self) -> IO[None]:
        return IO.pure(None)


__all__ = ('PluginStateHolder', 'ConcurrentPluginStateHolder', 'StrictPluginStateHolder')
