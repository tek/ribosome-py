import abc
import queue
import inspect
import logging
from typing import TypeVar, Generic, Type, Any, Callable, Optional
from threading import Lock

import greenlet

import toolz

from amino import Map, List, Boolean, Nil, Either, _, Lists, Maybe, Nothing, Try, do, Do, IO, __
from amino.dat import Dat
from amino.func import flip

from ribosome.trans.message_base import Message, Sendable, Envelope
from ribosome.dispatch.component import Component
from ribosome.nvim.io import NvimIOState, NS
from ribosome.dispatch.data import DispatchResult, DIO, Dispatch, DispatchSync, DispatchAsync
from ribosome.trans.queue import PrioQueue
from ribosome.trans.legacy import Handler
from ribosome.trans.handler import TransHandler, TransComplete
from ribosome.nvim import NvimIO
from ribosome.logging import Logging
from ribosome.request.rpc import RpcHandlerSpec
from ribosome.trans.action import LogMessage

D = TypeVar('D')
TransState = NvimIOState[D, DispatchResult]


class Handlers(Dat['Handlers']):

    def __init__(self, prio: int, handlers: Map[type, Handler]) -> None:
        self.prio = prio
        self.handlers = handlers

    def handler(self, msg):
        return self.handlers.get(type(msg))


def handlers(cls: Type['MachineBase']) -> List[Handler]:
    return Lists.wrap(inspect.getmembers(cls, Boolean.is_a(TransHandler))) / _[1]


def message_handlers(handlers: List[Handler]) -> Map[float, Handlers]:
    def create(prio, h):
        h = List.wrap(h).apzip(_.message).map2(flip)
        return prio, Handlers(prio, Map(h))
    return Map(toolz.groupby(_.prio, handlers)).map(create)


class ComponentState(Dat['ComponentState']):

    @staticmethod
    def cons(comp: Component) -> 'ComponentState':
        hs = message_handlers(handlers(comp))
        return ComponentState(comp, hs)

    def __init__(self, component: Component, handlers: Map[float, Handlers]) -> None:
        self.component = component
        self.handlers = handlers

    @property
    def name(self) -> str:
        return self.component.name


class Components(Dat['Components']):

    def __init__(self, all: List[ComponentState]) -> None:
        self.all = all

    def by_name(self, name: str) -> Either[str, ComponentState]:
        return self.all.find(_.name == name).to_either(f'no component named {name}')


class DispatchConfig(Dat['DispatchConfig']):

    @staticmethod
    def cons(
            config: 'ribosome.config.Config',
            sync_dispatch: Map[str, DispatchSync]=Map(),
            async_dispatch: Map[str, DispatchAsync]=Map(),
            io_executor: Callable[[DIO], NS['PluginState[D]', TransComplete]]=None,
    ) -> 'DispatchConfig':
        return DispatchConfig(config, sync_dispatch, async_dispatch, Maybe.optional(io_executor))

    def __init__(
            self,
            config: 'ribosome.config.Config',
            sync_dispatch: Map[str, DispatchSync],
            async_dispatch: Map[str, DispatchAsync],
            io_executor: Maybe[Callable[[DIO], NS['PluginState[D]', TransComplete]]]
    ) -> None:
        self.config = config
        self.sync_dispatch = sync_dispatch
        self.async_dispatch = async_dispatch
        self.io_executor = io_executor

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def prefix(self) -> str:
        return self.config.prefix

    @property
    def dispatch(self) -> List[Dispatch]:
        return self.sync_dispatch.v + self.async_dispatch.v

    @property
    def specs(self) -> List[RpcHandlerSpec]:
        return self.dispatch / __.spec(self.name, self.config.prefix)

    @property
    def distinct_specs(self) -> List[RpcHandlerSpec]:
        return self.specs.distinct_by(lambda s: s.rpc_method('test'))


class PluginState(Generic[D], Dat['PluginState']):

    @staticmethod
    def cons(
            dispatch_config: DispatchConfig,
            data: D,
            plugin: Any,
            components: List[Component],
            messages: PrioQueue[Message]=PrioQueue.empty,
            message_log: List[Message]=Nil,
            trans_log: List[str]=Nil,
            log_handler: Maybe[logging.Handler]=Nothing,
            logger: Maybe[Callable[[LogMessage], 'NS[PluginState[D], None]']]=Nothing,
    ) -> 'PluginState':
        component_state = Components(components / ComponentState.cons)
        return PluginState(dispatch_config, data, plugin, component_state, messages, message_log, trans_log,
                           log_handler, logger)

    def __init__(
            self,
            dispatch_config: DispatchConfig,
            data: D,
            plugin: Any,
            components: List[ComponentState],
            messages: PrioQueue[Message],
            message_log: List[Message],
            trans_log: List[str],
            log_handler: Maybe[logging.Handler],
            logger: Maybe[Callable[[LogMessage], 'NS[PluginState[D], None]']],
    ) -> None:
        self.dispatch_config = dispatch_config
        self.data = data
        self.plugin = plugin
        self.components = components
        self.messages = messages
        self.message_log = message_log
        self.trans_log = trans_log
        self.log_handler = log_handler
        self.logger = logger

    def enqueue(self, messages: List[Sendable]) -> 'PluginState[D]':
        envelopes = messages / Envelope.from_sendable
        return self.copy(messages=envelopes.fold_left(self.messages)(lambda q, m: q.put(m, m.prio)))

    def update(self, data: D) -> 'PluginState[D]':
        return self.copy(data=data)

    def log_messages(self, msgs: List[Message]) -> 'PluginState[D]':
        return self.append.message_log(msgs)

    def log_message(self, msg: Message) -> 'PluginState[D]':
        return self.log_messages(List(msg))

    def log_trans(self, trans: str) -> 'PluginState[D]':
        return self.append1.trans_log(trans)

    @property
    def has_messages(self) -> Boolean:
        return not self.messages.empty

    @property
    def unwrapped_messages(self) -> List[Message]:
        return self.messages.items / _[1] / _.msg

    @property
    def config(self) -> 'ribosome.config.Config':
        return self.dispatch_config.config

    @property
    def name(self) -> str:
        return self.config.name

    def component(self, name: str) -> Either[str, ComponentState]:
        return self.components.by_name(name)


class PluginStateHolder(Generic[D], Dat['PluginStateHolder'], Logging):

    @staticmethod
    def concurrent(state: PluginState[D], log_handler: logging.Handler=None) -> 'PluginStateHolder[D]':
        return ConcurrentPluginStateHolder(state, Maybe.check(log_handler), Lock(), False)

    @staticmethod
    def strict(state: PluginState[D], log_handler: logging.Handler=None) -> 'PluginStateHolder[D]':
        return StrictPluginStateHolder(state, log_handler)

    def __init__(self, state: PluginState[D], log_handler: Maybe[logging.Handler]=Nothing) -> None:
        self.state = state
        self.log_handler = log_handler

    def update(self, state: PluginState[D]) -> None:
        self.state = state

    @abc.abstractmethod
    def acquire(self) -> NvimIO[None]:
        ...

    @abc.abstractmethod
    def release(self, error: Optional[Exception]=None) -> NvimIO[None]:
        ...

    @abc.abstractmethod
    def dispatch_complete(self, dispatch: Dispatch) -> IO[None]:
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
            state: PluginState[D],
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
    def dispatch_complete(self, dispatch: Dispatch) -> Do:
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

    def dispatch_complete(self, dispatch: Dispatch) -> IO[None]:
        return IO.pure(None)


__all__ = ('ComponentState', 'PluginState', 'PluginStateHolder', 'Components')
