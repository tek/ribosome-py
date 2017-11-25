import inspect
from typing import TypeVar, Generic, Type
from threading import Lock

import toolz

from amino import Map, List, Boolean, Nil, Either, _, Lists
from amino.dat import Dat
from amino.func import flip

from ribosome.trans.message_base import Message, Sendable, Envelope
from ribosome.dispatch.component import Component
from ribosome.nvim.io import NvimIOState
from ribosome.dispatch.data import DispatchResult
from ribosome.trans.queue import PrioQueue
from ribosome.dispatch.transform import Handlers
from ribosome.trans.legacy import Handler

NP = TypeVar('NP')
D = TypeVar('D')
TransState = NvimIOState[D, DispatchResult]


def handlers(cls: Type['MachineBase']) -> List[Handler]:
    return Lists.wrap(inspect.getmembers(cls, Boolean.is_a(Handler))) / _[1]


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


class PluginState(Generic[D, NP], Dat['PluginState']):

    @staticmethod
    def cons(
            data: D,
            plugin: NP,
            components: List[Component],
            messages: PrioQueue[Message],
            message_log: List[Message]=Nil,
    ) -> 'PluginState':
        component_state = Components(components / ComponentState.cons)
        return PluginState(data, plugin, component_state, messages, message_log)

    def __init__(self,
                 data: D,
                 plugin: NP,
                 components: List[ComponentState],
                 messages: PrioQueue[Message],
                 message_log: List[Message]=Nil) -> None:
        self.data = data
        self.plugin = plugin
        self.components = components
        self.messages = messages
        self.message_log = message_log

    def enqueue(self, messages: List[Sendable]) -> 'PluginState[D, NP]':
        envelopes = messages / Envelope.from_sendable
        return self.copy(messages=envelopes.fold_left(self.messages)(lambda q, m: q.put(m, m.prio)))

    def update(self, data: D) -> 'PluginState[D, NP]':
        return self.copy(data=data)

    def log_messages(self, msgs: List[Message]) -> 'PluginState[D, NP]':
        return self.append.message_log(msgs)

    def log_message(self, msg: Message) -> 'PluginState[D, NP]':
        return self.log_messages(List(msg))

    @property
    def has_messages(self) -> Boolean:
        return not self.messages.empty

    @property
    def unwrapped_messages(self) -> List[Message]:
        return self.messages.items / _[1] / _.msg

    @property
    def config(self) -> 'ribosome.config.Config':
        return self.plugin.config

    @property
    def name(self) -> str:
        return self.config.name

    def component(self, name: str) -> Either[str, ComponentState]:
        return self.components.by_name(name)


class PluginStateHolder(Generic[D, NP], Dat['PluginStateHolder']):

    @staticmethod
    def cons(state: PluginState[D, NP]) -> 'PluginStateHolder':
        return PluginStateHolder(state, Lock())

    def __init__(self, state: PluginState[D, NP], lock: Lock) -> None:
        self.state = state
        self.lock = lock

    def update(self, state: PluginState[D, NP]) -> None:
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
