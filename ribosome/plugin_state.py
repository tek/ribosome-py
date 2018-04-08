import abc
import queue
import logging
from typing import TypeVar, Generic, Callable, Optional, Any, Type
from threading import Lock
from uuid import UUID

import greenlet

from amino import Map, List, Boolean, Nil, Either, _, Maybe, Nothing, Try, do, Do, IO, __, L
from amino.dat import Dat, ADT
from amino.util.string import camelcase

from ribosome.config.component import Component, Components, NoComponentData
from ribosome.nvim.io.state import NS
from ribosome.dispatch.data import DIO
from ribosome.compute.prog import Program
from ribosome.nvim.io.compute import NvimIO, lift_n_result
from ribosome.logging import Logging
from ribosome.request.rpc import RpcHandlerSpec, DefinedHandler
from ribosome.trans.action import LogMessage
from ribosome.config.settings import Settings
from ribosome.config.config import Config
from ribosome.trans.run import TransComplete
from ribosome.nvim.io.api import N
from ribosome.nvim.io.data import NResult
from ribosome.config.resources import Resources

A = TypeVar('A')
D = TypeVar('D')
C = TypeVar('C')
S = TypeVar('S', bound=Settings)
CC = TypeVar('CC')


Programs = Map[str, Program]


class DispatchConfig(Generic[S, D, CC], Dat['DispatchConfig']):

    @staticmethod
    def cons(
            config: Config[S, D, CC],
            programs: Programs=Map(),
            io_executor: Callable[[DIO], NS['PluginState[S, D, CC]', TransComplete]]=None,
            rpc_handlers: List[DefinedHandler]=Nil,
    ) -> 'DispatchConfig':
        return DispatchConfig(config, programs, Maybe.optional(io_executor), rpc_handlers)

    def __init__(
            self,
            config: 'ribosome.config.Config',
            programs: Programs,
            io_executor: Maybe[Callable[[DIO], NS['PluginState[S, D, CC]', TransComplete]]],
            rpc_handlers: List[DefinedHandler],
    ) -> None:
        self.config = config
        self.programs = programs
        self.io_executor = io_executor
        self.rpc_handlers = rpc_handlers

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def prefix(self) -> str:
        return self.config.prefix

    @property
    def specs(self) -> List[RpcHandlerSpec]:
        return self.programs.v.join / __.spec(self.name, self.config.prefix)

    @property
    def distinct_specs(self) -> List[RpcHandlerSpec]:
        return self.specs.distinct_by(_.rpc_method)


# FIXME in order to allow transparent updating of components, the data and config part must be separated
# FIXME using state type as a key won't work if multiple comps have the same type
class PluginState(Generic[S, D, CC], Dat['PluginState']):

    @staticmethod
    def cons(
            dispatch_config: DispatchConfig[S, D, CC],
            data: D,
            components: List[Component],
            trans_log: List[str]=Nil,
            log_handler: Maybe[logging.Handler]=Nothing,
            logger: Maybe[Callable[[LogMessage], 'NS[PluginState[S, D, CC], None]']]=Nothing,
            component_data: Map[type, Any]=Map(),
            active_mappings: Map[UUID, Program]=Map(),
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
            component_data: Map[type, Any],
            active_mappings: Map[UUID, Program],
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

    def ctor_by_type(self, tpe: Type[C]) -> Callable[[], C]:
        return self.components.by_type(tpe) / _.state_ctor | (lambda: NoComponentData)

    def data_by_type(self, tpe: Type[C]) -> C:
        return self.component_data.lift(tpe) | (lambda: self.ctor_by_type(tpe)())

    def data_for(self, component: Component) -> Any:
        return self.component_data.lift(component.state_type) | component.state_ctor

    def data_by_name(self, name: str) -> Either[str, Any]:
        return self.component(name) / self.data_for

    def update_component_data(self, tpe: Type[C], new: C) -> 'PluginState[S, D, CC]':
        return self.mod.component_data(__.cat((tpe, new)))

    def modify_component_data(self, name: str, mod: Callable[[Any], Any]) -> 'PluginState[S, D, CC]':
        comp = self.data_by_name(name)
        return comp / mod / L(self.update_component_data)(name, _) | self

    def resources_with(self, data: A) -> Resources[S, A, CC]:
        return Resources(data, self.settings, self.components)

    @property
    def resources(self) -> Resources[S, D, CC]:
        return self.resources_with(self.data)

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
    def release(self, result: Optional[NResult[A]]=None) -> NvimIO[None]:
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

    @do(NvimIO[None])
    def acquire(self) -> Do:
        '''acquire the state lock that prevents multiple programs from updating the state asynchronously.
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
        return N.pure(None)

    def release(self, result: Optional[NResult[A]]=None) -> NvimIO[None]:
        return N.pure(None)

    def dispatch_complete(self) -> IO[None]:
        return IO.pure(None)


__all__ = ('PluginState', 'PluginStateHolder')
