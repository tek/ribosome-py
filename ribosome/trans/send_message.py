import time
from typing import TypeVar, Callable

import amino
from amino import __, Maybe, Boolean, _, Nil, L, Try
from amino.do import do, Do

from ribosome.trans.message_base import Message, Sendable, Envelope
from ribosome.logging import ribo_log
from ribosome.plugin_state import PluginState, TransState
from ribosome.nvim.io import NS
from ribosome.dispatch.data import DispatchResult, DispatchError, DispatchOutputAggregate
from ribosome.dispatch.transform import validate_trans_complete
from ribosome.dispatch.component import Component, Components
from ribosome.trans.handler import MessageTrans
from ribosome.config.settings import Settings
from ribosome.trans.run import run_message_trans_handler

A = TypeVar('A')
D = TypeVar('D')
M = TypeVar('M', bound=Sendable)
NP = TypeVar('NP')
S = TypeVar('S', bound=Settings)
CC = TypeVar('CC')


def resolve_handler(component: Component, msg: Message, prio: float=None) -> Maybe[Callable]:
    f = __.handler(msg)
    return (
        component.handlers.v.find_map(f)
        if prio is None else
        (component.handlers.get(prio) // f)
    )


def internal(msg: Message) -> TransState:
    return DispatchResult.unit_nio


def handler_exception(e: Exception, desc: str) -> NS[D, DispatchResult]:
    if amino.development:
        err = f'transitioning {desc}'
        ribo_log.caught_exception(err, e)
    return NS.pure(DispatchResult(DispatchError.cons(e), Nil))


def try_handler(handler: Callable[[M], A], msg: M, desc: str) -> NS[D, DispatchResult]:
    return Try(handler, msg).map(validate_trans_complete).value_or(L(handler_exception)(_, desc))


def execute_component_handler(component: Component, handler: MessageTrans, msg: M) -> NS[D, DispatchResult]:
    return try_handler(L(run_message_trans_handler)(handler, _), msg, component.name)


def process(component: Component, msg: Message, prio: float) -> TransState:
    def execute(handler: Callable) -> TransState:
        ribo_log.debug(f'handling {msg} in {component.name}')
        return execute_component_handler(component, handler, msg)
    return resolve_handler(component, msg, prio) / execute | (lambda: internal(msg))


def send_msg(components: Components, msg: Message, prio: float) -> TransState:
    return (
        components.all
        .traverse(lambda comp: process(comp, msg, prio), NS) /
        DispatchOutputAggregate /
        L(DispatchResult)(_, Nil)
    )


def send_envelope(components: Components, env: Envelope, prio: float) -> TransState:
    msg = env.msg
    def to_comp(name: str) -> TransState:
        return components.by_name(name) / L(process)(_, msg, prio) | (lambda: DispatchResult.unit_nio)
    return env.recipient / to_comp | (lambda: send_msg(components, msg, prio))


@do(TransState)
def send_message1(components: Components, msg: M, prio: float) -> Do:
    ''' send **msg** to all submachines, passing the transformed data from each machine to the next and accumulating
    published messages.
    '''
    send = Boolean.isinstance(msg, Envelope).cata(send_envelope, send_msg)
    yield send(components, msg, prio)


def transform_data_state(st: NS[D, DispatchResult]) -> NS[PluginState[S, D, CC], DispatchResult]:
    return st.transform_s(_.data, lambda r, s: r.copy(data=s))


@do(NS[PluginState[S, D, CC], DispatchResult])
def send_message(msg: M, prio: float=None) -> Do:
    yield NS.modify(__.log_message(msg.msg))
    components = yield NS.inspect(_.components)
    yield transform_data_state(send_message1(components, msg, prio))


__all__ = ('send_message',)
