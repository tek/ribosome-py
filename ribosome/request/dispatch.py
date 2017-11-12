import abc
from typing import TypeVar, Any, Generic, Tuple
from threading import Lock

from neovim.msgpack_rpc.event_loop.base import BaseEventLoop

from amino import Map, List, Boolean, Nil, Either, _
from amino.algebra import Algebra
from amino.dat import Dat

from ribosome.nvim import NvimFacade, NvimIO
from ribosome.logging import Logging, ribo_log
from ribosome.rpc import RpcHandlerFunction, RpcHandlerSpec
# from ribosome.plugin import NvimPlugin
from ribosome.machine.message_base import _message_attr, Message
from ribosome.machine.process_messages import PrioQueue
from ribosome.machine.handler import AlgResultValidator, Handlers
from ribosome.request.handler import RequestHandler, TransDispatcher
from ribosome.machine.transition import TransitionLog
from ribosome.machine.machine import Machine
from ribosome.machine.sub import Component, ComponentMachine
from ribosome.machine.base import message_handlers
from ribosome.machine.modular import trans_handlers

Loop = TypeVar('Loop', bound=BaseEventLoop)
# NP = TypeVar('NP', bound=NvimPlugin)
NP = TypeVar('NP')
D = TypeVar('D')
AS = TypeVar('AS')
A = TypeVar('A', bound=AS)
B = TypeVar('B')


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


class PluginState(Generic[D, NP], Dat['PluginState']):

    @staticmethod
    def cons(
            vim: NvimFacade,
            data: D,
            plugin: NP,
            components: List[ComponentMachine],
            messages: PrioQueue[Message],
            message_log: List[Message]=Nil,
    ) -> 'PluginState':
        component_state = components / ComponentState.cons
        return PluginState(vim, data, plugin, component_state, messages, message_log)

    def __init__(self,
                 vim: NvimFacade,
                 data: D,
                 plugin: NP,
                 components: List[ComponentState],
                 messages: PrioQueue[Message],
                 message_log: List[Message]=Nil) -> None:
        self.vim = vim
        self.data = data
        self.plugin = plugin
        self.components = components
        self.messages = messages
        self.message_log = message_log

    def enqueue(self, messages: List[Message]) -> 'PluginState[D, NP]':
        return self.copy(messages=messages.fold_left(self.messages)(lambda q, m: q.put(m, m.prio)))

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
        return self.components.find(_.name == name).to_either(f'no component named {name}')


class PluginStateHolder(Generic[D, NP], Dat['PluginStateHolder']):

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


class Dispatch(Algebra, base=True):

    @abc.abstractproperty
    def sync(self) -> Boolean:
        ...

    @abc.abstractmethod
    def spec(self, name: str, prefix: str) -> RpcHandlerSpec:
        ...


class Legacy(Dispatch):

    def __init__(self, handler: RpcHandlerFunction) -> None:
        self.handler = handler

    def _arg_desc(self) -> List[str]:
        return List(str(self.handler))

    @property
    def sync(self) -> Boolean:
        return self.handler.spec.sync

    def spec(self, name: str, prefix: str) -> RpcHandlerSpec:
        return self.handler.spec


class SendMessage(Dispatch):

    def __init__(self, name: str, handler: RequestHandler) -> None:
        self.name = name
        self.handler = handler

    def _arg_desc(self) -> List[str]:
        return List(self.name, str(self.handler))

    @property
    def sync(self) -> Boolean:
        return self.handler.sync

    def spec(self, name: str, prefix: str) -> RpcHandlerSpec:
        return self.handler.spec(name, prefix)


class Trans(Dispatch):

    def __init__(self, name: str, handler: RequestHandler[TransDispatcher[B]]) -> None:
        self.name = name
        self.handler = handler

    def _arg_desc(self) -> List[str]:
        return List(self.name, str(self.handler))

    @property
    def sync(self) -> Boolean:
        return self.handler.sync

    def spec(self, name: str, prefix: str) -> RpcHandlerSpec:
        return self.handler.spec(name, prefix)


class Internal(Dispatch):

    def __init__(self, handler: RequestHandler) -> None:
        self.handler = handler

    def _arg_desc(self) -> List[str]:
        return List(str(self.handler))

    @property
    def sync(self) -> Boolean:
        return self.handler.sync

    def spec(self, name: str, prefix: str) -> RpcHandlerSpec:
        return self.handler.spec(name, prefix)

    @property
    def name(self) -> str:
        return self.handler.name


class Custom(Dispatch): pass


DispatchResult = Tuple[Any, PluginState[D, NP], List[Message]]


def handle_trans(trans: Trans, state: PluginState[D, NP], args: List[Any]) -> DispatchResult:
    handler = trans.handler.dispatcher.handler
    msg = handler.message(*args)
    result = handler.execute(None, state.data, msg)
    validator = AlgResultValidator(trans.name)
    trans_result = validator.validate(result, state.data)
    return None, state.log_message(msg).update(trans_result.data), trans_result.resend + trans_result.pub


def handle_internal(trans: Trans, state: PluginState[D, NP], args: List[Any]) -> DispatchResult:
    handler = trans.handler.dispatcher.handler
    result = handler.execute(None, state, args)
    validator = AlgResultValidator(trans.name)
    trans_result = validator.validate(result, state.data)
    return trans_result.output | None, state, Nil


class RunDispatch(Generic[D, NP], Logging):

    def __init__(self, state: PluginState[D, NP], args: List[Any]) -> None:
        self.state = state
        self.args = args

    def legacy(self, dispatch: Legacy) -> NvimIO[DispatchResult]:
        def send(v: Any) -> DispatchResult:
            self.state.root.state = self.state.data
            result = dispatch.handler.func(self.state.plugin, *self.args)
            return result, self.state.update(self.state.root.state).log_messages(self.state.root.last_message_log), Nil
        return NvimIO(send)

    def send_message(self, dispatch: SendMessage) -> NvimIO[DispatchResult]:
        def send(v: Any) -> DispatchResult:
            msg = dispatch.handler.dispatcher.msg(*self.args)
            tr = TransitionLog.empty
            log, result = self.state.plugin.root.loop_process(self.state.data, msg).run(tr).evaluate()
            return None, self.state.log_message(msg).update(result.data).log(log), result.pub
        return NvimIO(send)

    def trans(self, dispatch: Trans) -> NvimIO[DispatchResult]:
        return NvimIO(lambda v: handle_trans(dispatch, self.state, self.args))

    def internal(self, dispatch: Internal) -> NvimIO[DispatchResult]:
        return NvimIO(lambda v: handle_internal(dispatch, self.state, self.args))

    def custom(self, dispatch: Custom) -> NvimIO[DispatchResult]:
        pass


def invalid_dispatch(data: Any) -> NvimIO[Any]:
    return NvimIO.failed(f'invalid type passed to `RunDispatch`: {data}')


class DispatchJob(Dat['DispatchJob']):

    def __init__(
            self,
            dispatches: Map[str, Dispatch],
            state: PluginStateHolder[D, NP],
            name: str,
            args: List[Any],
            sync: bool,
            plugin_name: str,
            bang: Boolean,
    ) -> None:
        self.dispatches = dispatches
        self.state = state
        self.name = name
        self.args = args
        self.sync = sync
        self.plugin_name = plugin_name
        self.bang = Boolean(bang)


__all__ = ('PluginState', 'PluginStateHolder', 'Dispatch', 'Legacy', 'SendMessage', 'Trans', 'Custom', 'RunDispatch',
           'invalid_dispatch', 'DispatchJob')
