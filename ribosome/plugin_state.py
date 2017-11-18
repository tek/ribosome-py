from typing import TypeVar, Generic
from threading import Lock

from amino import Map, List, Boolean, Nil, Either, _
from amino.dat import Dat

from ribosome.nvim import NvimFacade
from ribosome.machine.message_base import Message, Sendable, Envelope
from ribosome.machine.process_messages import PrioQueue
from ribosome.machine.handler import Handlers
from ribosome.machine.transition import TransitionLog
from ribosome.machine.machine import Machine
from ribosome.machine.sub import Component, ComponentMachine
from ribosome.machine.base import message_handlers
from ribosome.machine.modular import trans_handlers

NP = TypeVar('NP')
D = TypeVar('D')


class ComponentState(Dat['ComponentState']):

    @staticmethod
    def cons(comp: ComponentMachine) -> 'ComponentState':
        handlers = message_handlers(trans_handlers(comp.transitions))
        return ComponentState(comp, handlers)

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
            components: List[ComponentMachine],
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

    def log(self, log: TransitionLog) -> 'PluginState[D, NP]':
        return self.log_messages(log.message_log)

    def log_messages(self, msgs: List[Message]) -> 'PluginState[D, NP]':
        return self.append.message_log(msgs)

    def log_message(self, msg: Message) -> 'PluginState[D, NP]':
        return self.log_messages(List(msg))

    @property
    def has_messages(self) -> Boolean:
        return not self.messages.empty

    @property
    def config(self) -> 'ribosome.config.Config':
        return self.plugin.config

    @property
    def root(self) -> Machine:
        return self.plugin.root

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


__all__ = ('ComponentState', 'PluginState', 'PluginStateHolder', 'Components')
