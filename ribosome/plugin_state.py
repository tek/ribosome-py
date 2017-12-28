import abc
import queue
import logging
from typing import TypeVar, Generic, Callable, Optional, Any
from threading import Lock

import greenlet

from amino import Map, List, Boolean, Nil, Either, _, Maybe, Nothing, Try, do, Do, IO, __
from amino.dat import Dat, ADT

from ribosome.trans.message_base import Message, Sendable, Envelope
from ribosome.dispatch.component import Component, Components
from ribosome.nvim.io import NvimIOState, NS
from ribosome.dispatch.data import DispatchResult, DIO, Dispatch, DispatchSync, DispatchAsync
from ribosome.trans.queue import PrioQueue
from ribosome.trans.handler import TransComplete
from ribosome.nvim import NvimIO
from ribosome.logging import Logging
from ribosome.request.rpc import RpcHandlerSpec, DefinedHandler
from ribosome.trans.action import LogMessage
from ribosome.config.settings import Settings
from ribosome.config.config import Config

D = TypeVar('D')
C = TypeVar('C')
DP = TypeVar('DP', bound=Dispatch)
TransState = NvimIOState[D, DispatchResult]
S = TypeVar('S', bound=Settings)


class DispatchAffiliaton(Generic[DP], ADT['DispatchAffiliaton[DP]']):

    def __init__(self, dispatch: DP) -> None:
        self.dispatch = dispatch

    @property
    def sync(self) -> Boolean:
        return self.dispatch.sync

    @property
    def async(self) -> Boolean:
        return self.dispatch.async

    @property
    def desc(self) -> str:
        return self.dispatch.desc


class RootDispatch(Generic[DP], DispatchAffiliaton[DP]):
    pass


class ComponentDispatch(Generic[DP], DispatchAffiliaton[DP]):

    def __init__(self, name: str, dispatch: DP, state_ctor: Callable[[], C]) -> None:
        self.name = name
        self.state_ctor = state_ctor
        super().__init__(dispatch)


Syncs = Map[str, DispatchAffiliaton[DispatchSync]]
Asyncs = Map[str, List[DispatchAffiliaton[DispatchAsync]]]


class DispatchConfig(Generic[S, D], Dat['DispatchConfig']):

    @staticmethod
    def cons(
            config: Config[S, D],
            sync_dispatch: Syncs=Map(),
            async_dispatch: Asyncs=Map(),
            io_executor: Callable[[DIO], NS['PluginState[S, D]', TransComplete]]=None,
            rpc_handlers: List[DefinedHandler]=Nil,
    ) -> 'DispatchConfig':
        return DispatchConfig(config, sync_dispatch, async_dispatch, Maybe.optional(io_executor), rpc_handlers)

    def __init__(
            self,
            config: 'ribosome.config.Config',
            sync_dispatch: Map[str, DispatchSync],
            async_dispatch: Map[str, List[DispatchAsync]],
            io_executor: Maybe[Callable[[DIO], NS['PluginState[S, D]', TransComplete]]],
            rpc_handlers: List[DefinedHandler],
    ) -> None:
        self.config = config
        self.sync_dispatch = sync_dispatch
        self.async_dispatch = async_dispatch
        self.io_executor = io_executor
        self.rpc_handlers = rpc_handlers

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def prefix(self) -> str:
        return self.config.prefix

    @property
    def dispatch(self) -> List[Dispatch]:
        return self.sync_dispatch.v + self.async_dispatch.v.join

    @property
    def specs(self) -> List[RpcHandlerSpec]:
        return self.dispatch / __.dispatch.spec(self.name, self.config.prefix)

    @property
    def distinct_specs(self) -> List[RpcHandlerSpec]:
        return self.specs.distinct_by(_.rpc_method)


class PluginState(Generic[S, D], Dat['PluginState']):

    @staticmethod
    def cons(
            dispatch_config: DispatchConfig[S, D],
            data: D,
            components: List[Component],
            messages: PrioQueue[Message]=PrioQueue.empty,
            message_log: List[Message]=Nil,
            trans_log: List[str]=Nil,
            log_handler: Maybe[logging.Handler]=Nothing,
            logger: Maybe[Callable[[LogMessage], 'NS[PluginState[S, D], None]']]=Nothing,
            component_data: Map[str, Any]=Map(),
    ) -> 'PluginState':
        component_state = Components(components)
        return PluginState(dispatch_config, data, component_state, messages, message_log, trans_log,
                           log_handler, logger, component_data)

    def __init__(
            self,
            dispatch_config: DispatchConfig,
            data: D,
            components: Components,
            messages: PrioQueue[Message],
            message_log: List[Message],
            trans_log: List[str],
            log_handler: Maybe[logging.Handler],
            logger: Maybe[Callable[[LogMessage], 'NS[PluginState[S, D], None]']],
            component_data: Map[str, Any],
    ) -> None:
        self.dispatch_config = dispatch_config
        self.data = data
        self.components = components
        self.messages = messages
        self.message_log = message_log
        self.trans_log = trans_log
        self.log_handler = log_handler
        self.logger = logger
        self.component_data = component_data

    def enqueue(self, messages: List[Sendable]) -> 'PluginState[S, D]':
        envelopes = messages / Envelope.from_sendable
        return self.copy(messages=envelopes.fold_left(self.messages)(lambda q, m: q.put(m, m.prio)))

    def update(self, data: D) -> 'PluginState[S, D]':
        return self.copy(data=data)

    def log_messages(self, msgs: List[Message]) -> 'PluginState[S, D]':
        return self.append.message_log(msgs)

    def log_message(self, msg: Message) -> 'PluginState[S, D]':
        return self.log_messages(List(msg))

    def log_trans(self, trans: str) -> 'PluginState[S, D]':
        return self.append1.trans_log(trans)

    @property
    def has_messages(self) -> Boolean:
        return not self.messages.empty

    @property
    def unwrapped_messages(self) -> List[Message]:
        return self.messages.items / _[1] / _.msg

    @property
    def config(self) -> Config:
        return self.dispatch_config.config

    @property
    def settings(self) -> S:
        return self.config.settings


    @property
    def name(self) -> str:
        return self.config.name

    def component(self, name: str) -> Either[str, Component]:
        return self.components.by_name(name)

    def update_component_data(self, name: str, new: Any) -> 'PluginState[S, D]':
        return self.mod.component_data(__.cat((name, new)))


class PluginStateHolder(Generic[D], Dat['PluginStateHolder'], Logging):

    @staticmethod
    def concurrent(state: PluginState[S, D], log_handler: logging.Handler=None) -> 'PluginStateHolder[D]':
        return ConcurrentPluginStateHolder(state, Maybe.check(log_handler), Lock(), False)

    @staticmethod
    def strict(state: PluginState[S, D], log_handler: logging.Handler=None) -> 'PluginStateHolder[D]':
        return StrictPluginStateHolder(state, log_handler)

    def __init__(self, state: PluginState[S, D], log_handler: Maybe[logging.Handler]=Nothing) -> None:
        self.state = state
        self.log_handler = log_handler

    def update(self, state: PluginState[S, D]) -> None:
        self.state = state

    @abc.abstractmethod
    def acquire(self) -> NvimIO[None]:
        ...

    @abc.abstractmethod
    def release(self, error: Optional[Exception]=None) -> NvimIO[None]:
        ...

    @abc.abstractmethod
    def dispatch_complete(self) -> IO[None]:
        ...

    @property
    def has_messages(self) -> Boolean:
        return self.state.has_messages

    @property
    def message_queue(self) -> PrioQueue[Message]:
        return self.state.messages

    @property
    def messages(self) -> List[Message]:
        return self.state.unwrapped_messages


class ConcurrentPluginStateHolder(Generic[D], PluginStateHolder[D]):

    def __init__(
            self,
            state: PluginState[S, D],
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

    # FIXME if an async request arrives while another async dispatch is executing, will it behave similarly?
    # If so, this needs multiple waiting greenlets.
    # If not, the parent switch (and overwriting of `waiting_greenlets`) may not be done.
    @do(NvimIO[None])
    def acquire(self) -> Do:
        '''acquire the state lock that prevents multiple dispatches from updating the state asynchronously.
        If the lock is already acquired, an async dispatch is currently executing while another (sync or async) has been
        requested. In order not to block on requests to vim from the running dispatch, the greenlet that was started by
        the vim session must be suspended, giving control back to the running async dispatch at the point where the vim
        request was made.
        '''
        def switch() -> None:
            self.log.debug(f'acquire: switching to running dispatch')
            self._enqueue_greenlet()
            Try(lambda: greenlet.getcurrent().parent.switch()).leffect(self._pop_greenlet)
        if self.running:
            yield NvimIO.simple(switch)
        yield NvimIO.simple(self.lock.acquire)
        yield NvimIO.simple(setattr, self, 'running', True)

    @do(NvimIO[None])
    def release(self, error: Optional[Exception]=None) -> Do:
        yield NvimIO.simple(setattr, self, 'running', False)
        yield NvimIO.simple(Try, self.lock.release)
        if error:
            self.log.debug(f'released lock due to error: {error}')
            yield NvimIO.exception(error)

    @do(IO[None])
    def dispatch_complete(self) -> Do:
        '''switch back to the dispatch that was suspended in `acquire` while the dispatch executing this method was
        running.
        '''
        if not self.waiting_greenlets.empty():
            self.log.debug('release: switching to waiting dispatch')
            gr = yield IO.delay(self._pop_greenlet)
            yield IO.delay(gr.switch)
        yield IO.pure(None)


class StrictPluginStateHolder(Generic[D], PluginStateHolder[D]):
    pass

    def acquire(self) -> NvimIO[None]:
        return NvimIO.pure(None)

    def release(self, error: Optional[Exception]=None) -> NvimIO[None]:
        return NvimIO.pure(None)

    def dispatch_complete(self) -> IO[None]:
        return IO.pure(None)

__all__ = ('PluginState', 'PluginStateHolder')
