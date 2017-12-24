import time
from typing import TypeVar, Callable

import amino
from amino import __, Maybe, Boolean, _, Nil, L, Try
from amino.do import do, Do

from ribosome.trans.message_base import Message, Sendable, Envelope
from ribosome.logging import ribo_log
from ribosome.plugin_state import PluginState, ComponentState, Components, TransState
from ribosome.nvim.io import NvimIOState
from ribosome.dispatch.data import DispatchResult, DispatchError, DispatchOutputAggregate
from ribosome.dispatch.transform import validate_trans_complete
from ribosome.dispatch.component import Component
from ribosome.trans.handler import MessageTransHandler
from ribosome.trans.legacy import TransitionFailed

A = TypeVar('A')
D = TypeVar('D')
M = TypeVar('M', bound=Sendable)
NP = TypeVar('NP')


def resolve_handler(component: ComponentState, msg: Message, prio: float=None) -> Maybe[Callable]:
    f = __.handler(msg)
    return (
        component.handlers.v.find_map(f)
        if prio is None else
        (component.handlers.get(prio) // f)
    )


def internal(msg: Message) -> TransState:
    return DispatchResult.unit_nio


def format_report(msg: Message, dur: float, name: str) -> str:
    return '{} took {:.4f}s for {} to process'.format(msg, dur, name)


def check_time(start_time: int, msg: Message, name: str) -> None:
    dur = time.time() - start_time
    ribo_log.debug1(format_report, msg, dur, name)
    # if dur > self._min_report_time:
    #     self._reports = self._reports.cat((msg, dur))


def handler_exception(e: Exception, desc: str) -> NvimIOState[D, DispatchResult]:
    if amino.development:
        err = f'transitioning {desc}'
        ribo_log.caught_exception(err, e)
        raise TransitionFailed(str(e)) from e
    return NvimIOState.pure(DispatchResult(DispatchError.cons(e), Nil))


def try_handler(handler: Callable[[M], A], msg: M, desc: str) -> NvimIOState[D, DispatchResult]:
    return Try(handler, msg).map(validate_trans_complete).value_or(L(handler_exception)(_, desc))


def execute_component_handler(component: Component, handler: MessageTransHandler, msg: M
                              ) -> NvimIOState[D, DispatchResult]:
    result = try_handler(L(handler.run)(component, _), msg, component.name)
    # check_time(job.start_time, msg, component.name)
    return result


def process(component: ComponentState, msg: Message, prio: float) -> TransState:
    def execute(handler: Callable) -> TransState:
        ribo_log.debug(f'handling {msg} in {component.name}')
        return execute_component_handler(component.component, handler, msg)
    return resolve_handler(component, msg, prio) / execute | (lambda: internal(msg))


def send_msg(components: Components, msg: Message, prio: float) -> TransState:
    return (
        components.all
        .traverse(lambda comp: process(comp, msg, prio), NvimIOState) /
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


def transform_data_state(st: NvimIOState[D, DispatchResult]) -> NvimIOState[PluginState[D], DispatchResult]:
    return st.transform_s(_.data, lambda r, s: r.copy(data=s))


@do(NvimIOState[PluginState[D], DispatchResult])
def send_message(msg: M, prio: float=None) -> Do:
    yield NvimIOState.modify(__.log_message(msg.msg))
    components = yield NvimIOState.inspect(_.components)
    yield transform_data_state(send_message1(components, msg, prio))


__all__ = ('send_message',)
