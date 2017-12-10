import inspect
import logging
from typing import TypeVar, Generic, Type, Any, Callable
from threading import Lock

import toolz

from amino import Map, List, Boolean, Nil, Either, _, Lists, Maybe, Nothing
from amino.dat import Dat
from amino.func import flip

from ribosome.trans.message_base import Message, Sendable, Envelope
from ribosome.dispatch.component import Component
from ribosome.nvim.io import NvimIOState, NS
from ribosome.dispatch.data import DispatchResult, DIO
from ribosome.trans.queue import PrioQueue
from ribosome.trans.legacy import Handler
from ribosome.trans.handler import TransHandler, TransComplete

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
            io_executor: Callable[[DIO], NS['PluginState[D]', TransComplete]]=None,
    ) -> 'DispatchConfig':
        return DispatchConfig(config, Maybe.optional(io_executor))

    def __init__(
            self,
            config: 'ribosome.config.Config',
            io_executor: Maybe[Callable[[DIO], NS['PluginState[D]', TransComplete]]]
    ) -> None:
        self.config = config
        self.io_executor = io_executor

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def prefix(self) -> str:
        return self.config.prefix


class PluginState(Generic[D], Dat['PluginState']):

    @staticmethod
    def cons(
            dispatch_config: DispatchConfig,
            data: D,
            plugin: Any,
            components: List[Component],
            messages: PrioQueue[Message],
            message_log: List[Message]=Nil,
            trans_log: List[str]=Nil,
            log_handler: Maybe[logging.Handler]=Nothing,
    ) -> 'PluginState':
        component_state = Components(components / ComponentState.cons)
        return PluginState(dispatch_config, data, plugin, component_state, messages, message_log, trans_log,
                           log_handler)

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
    ) -> None:
        self.dispatch_config = dispatch_config
        self.data = data
        self.plugin = plugin
        self.components = components
        self.messages = messages
        self.message_log = message_log
        self.trans_log = trans_log
        self.log_handler = log_handler

    def enqueue(self, messages: List[Sendable]) -> 'PluginState[D]':
        envelopes = messages / Envelope.from_sendable
        return self.copy(messages=envelopes.fold_left(self.messages)(lambda q, m: q.put(m, m.prio)))

    def update(self, data: D) -> 'PluginState[D]':
        return self.copy(data=data)

    def log_messages(self, msgs: List[Message]) -> 'PluginState[D]':
        return self.append.message_log(msgs)

    def log_message(self, msg: Message) -> 'PluginState[D]':
        return self.log_messages(List(msg))

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


class PluginStateHolder(Generic[D], Dat['PluginStateHolder']):

    @staticmethod
    def cons(state: PluginState[D], log_handler: logging.Handler=None) -> 'PluginStateHolder':
        return PluginStateHolder(state, Lock(), Maybe.check(log_handler))

    def __init__(self, state: PluginState[D], lock: Lock, log_handler: Maybe[logging.Handler]=Nothing) -> None:
        self.state = state
        self.lock = lock
        self.log_handler = log_handler

    def update(self, state: PluginState[D]) -> None:
        self.state = state

    def acquire(self) -> None:
        self.lock.acquire(timeout=10.0)

    def release(self) -> None:
        self.lock.release()

    @property
    def has_messages(self) -> Boolean:
        return self.state.has_messages

    @property
    def message_queue(self) -> PrioQueue[Message]:
        return self.state.messages

    @property
    def messages(self) -> List[Message]:
        return self.state.unwrapped_messages


__all__ = ('ComponentState', 'PluginState', 'PluginStateHolder', 'Components')
