import abc
import queue
import logging
from typing import TypeVar, Generic, Callable, Optional, Any
from threading import Lock
from uuid import UUID

import greenlet

from amino import Map, List, Boolean, Nil, Either, _, Maybe, Nothing, Try, do, Do, IO, __, L
from amino.dat import Dat, ADT
from amino.util.string import camelcase

from ribosome.dispatch.component import Component, Components
from ribosome.nvim.io import NS
from ribosome.dispatch.data import DIO, Dispatch, DispatchSync, DispatchAsync
from ribosome.trans.handler import TransF
from ribosome.nvim import NvimIO
from ribosome.logging import Logging
from ribosome.request.rpc import RpcHandlerSpec, DefinedHandler
from ribosome.trans.action import LogMessage
from ribosome.config.settings import Settings
from ribosome.config.config import Config, Resources
from ribosome.trans.run import TransComplete

A = TypeVar('A')
D = TypeVar('D')
C = TypeVar('C')
DP = TypeVar('DP', bound=Dispatch)
S = TypeVar('S', bound=Settings)
CC = TypeVar('CC')


class DispatchAffiliation(ADT['DispatchAffiliation']):

    @property
    def is_component(self) -> Boolean:
        return Boolean.isinstance(self, ComponentDispatch)

    @abc.abstractproperty
    def name(self) -> str:
        ...


class RootDispatch(DispatchAffiliation):

    @property
    def name(self) -> str:
        return '<root>'


class ComponentDispatch(DispatchAffiliation):

    def __init__(self, component: Component) -> None:
        self.component = component

    @property
    def name(self) -> str:
        return self.component.name


class AffiliatedDispatch(Generic[DP], Dat['AffiliatedDispatch[DP]']):

    def __init__(self, dispatch: DP, aff: DispatchAffiliation) -> None:
        self.dispatch = dispatch
        self.aff = aff

    @property
    def sync(self) -> Boolean:
        return self.dispatch.sync

    @property
    def async(self) -> Boolean:
        return self.dispatch.async

    @property
    def desc(self) -> str:
        return self.dispatch.desc


Dispatches = Map[str, List[AffiliatedDispatch[DispatchAsync]]]


class DispatchConfig(Generic[S, D, CC], Dat['DispatchConfig']):

    @staticmethod
    def cons(
            config: Config[S, D, CC],
            dispatches: Dispatches=Map(),
            io_executor: Callable[[DIO], NS['PluginState[S, D, CC]', TransComplete]]=None,
            rpc_handlers: List[DefinedHandler]=Nil,
    ) -> 'DispatchConfig':
        return DispatchConfig(config, dispatches, Maybe.optional(io_executor), rpc_handlers)

    def __init__(
            self,
            config: 'ribosome.config.Config',
            dispatches: Dispatches,
            io_executor: Maybe[Callable[[DIO], NS['PluginState[S, D, CC]', TransComplete]]],
            rpc_handlers: List[DefinedHandler],
    ) -> None:
        self.config = config
        self.dispatches = dispatches
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
        return self.dispatches.v.join

    @property
    def specs(self) -> List[RpcHandlerSpec]:
        return self.dispatch / __.dispatch.spec(self.name, self.config.prefix)

    @property
    def distinct_specs(self) -> List[RpcHandlerSpec]:
        return self.specs.distinct_by(_.rpc_method)


class PluginState(Generic[S, D, CC], Dat['PluginState']):

    @staticmethod
    def cons(
            dispatch_config: DispatchConfig[S, D, CC],
            data: D,
            components: List[Component],
            trans_log: List[str]=Nil,
            log_handler: Maybe[logging.Handler]=Nothing,
            logger: Maybe[Callable[[LogMessage], 'NS[PluginState[S, D, CC], None]']]=Nothing,
            component_data: Map[str, Any]=Map(),
            active_mappings: Map[UUID, TransF]=Map(),
    ) -> 'PluginState':
        components = Components.cons(components, dispatch_config.config.component_config_type)
        return PluginState(
            dispatch_config,
            data,
            components,
            trans_log,
            log_handler,
            logger,
            component_data,
            active_mappings,
        )

    def __init__(
            self,
            dispatch_config: DispatchConfig[S, D, CC],
            data: D,
            components: Components,
            trans_log: List[str],
            log_handler: Maybe[logging.Handler],
            logger: Maybe[Callable[[LogMessage], 'NS[PluginState[S, D, CC], None]']],
            component_data: Map[str, Any],
            active_mappings: Map[UUID, TransF],
    ) -> None:
        self.dispatch_config = dispatch_config
        self.data = data
        self.components = components
        self.trans_log = trans_log
        self.log_handler = log_handler
        self.logger = logger
        self.component_data = component_data
        self.active_mappings = active_mappings

    def update(self, data: D) -> 'PluginState[S, D, CC]':
        return self.copy(data=data)

    def log_trans(self, trans: str) -> 'PluginState[S, D, CC]':
        return self.append1.trans_log(trans)

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

    def data_for(self, component: Component) -> Any:
        return self.component_data.lift(component.name) | component.state_ctor

    def data_by_name(self, name: str) -> Either[str, Any]:
        return self.component(name) / self.data_for

    def update_component_data(self, name: str, new: Any) -> 'PluginState[S, D, CC]':
        return self.mod.component_data(__.cat((name, new)))

    def modify_component_data(self, name: str, mod: Callable[[Any], Any]) -> 'PluginState[S, D, CC]':
        comp = self.data_by_name(name)
        return comp / mod / L(self.update_component_data)(name, _) | self

    def resources_with(self, data: A) -> Resources[S, A, CC]:
        return Resources(data, self.settings, self.components)

    @property
    def resources(self) -> Resources[S, D, CC]:
        return self.resources_with(self.data)

    def reaffiliate(self, handler: TransF, current: DispatchAffiliation) -> DispatchAffiliation:
        c = self.components.for_handler(handler)
        return c.cata(ComponentDispatch, current)

    @property
    def camelcase_name(self) -> str:
        return camelcase(self.name)


class PluginStateHolder(Generic[D], Dat['PluginStateHolder'], Logging):

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
    def release(self, error: Optional[Exception]=None) -> NvimIO[None]:
        ...

    @abc.abstractmethod
    def dispatch_complete(self) -> IO[None]:
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
