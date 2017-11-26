import time
from typing import TypeVar, Callable, Generator

from amino import __, Maybe, Boolean, _, List, Nil, L
from amino.do import do

from ribosome.trans.message_base import Message, Sendable, Envelope
from ribosome.logging import ribo_log
from ribosome.plugin_state import PluginState, ComponentState, Components, TransState
from ribosome.nvim.io import NvimIOState
from ribosome.dispatch.data import DispatchResult, DispatchUnit, DispatchError, DispatchErrors, DispatchOutputAggregate
from ribosome.dispatch.transform import AlgHandlerJob

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


def process(component: ComponentState, msg: Message, prio: float) -> TransState:
    def execute(handler: Callable) -> TransState:
        ribo_log.debug(f'handling {msg} in {component.name}')
        job = AlgHandlerJob(component.name, handler, msg)
        result = job.run()
        check_time(job.start_time, msg, component.name)
        return result
    return resolve_handler(component, msg, prio) / execute | (lambda: internal(msg))


@do(TransState)
def send_message_to_component(component: ComponentState, data: D, msg: M, prio: float) -> TransState:
    result = yield process(component, data, msg, prio)
    log = yield NvimIOState.get()
    resend = result.resend
    new_log, next_msg = log.resend(resend).pop
    yield NvimIOState.set(new_log)
    yield NvimIOState.pure(result)


def send_to(msg: Message, prio: float) -> Callable[[TransState, ComponentState], TransState]:
    @do(TransState)
    def send(z: TransState, comp: ComponentState) -> Generator:
        current = yield z
        next = yield send_message_to_component(comp, current.data, msg, prio)
        yield NvimIOState.pure(current.accum(next))
    return send


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
        return components.by_name(name) / send_to(msg, prio) | (lambda: DispatchResult.unit_nio)
    return env.recipient / to_comp | (lambda: send_msg(components, msg, prio))


@do(TransState)
def send_message1(components: Components, msg: M, prio: float) -> Generator:
    ''' send **msg** to all submachines, passing the transformed data from each machine to the next and accumulating
    published messages.
    '''
    send = Boolean.isinstance(msg, Envelope).cata(send_envelope, send_msg)
    yield send(components, msg, prio)


def transform_data_state(st: NvimIOState[D, DispatchResult]) -> NvimIOState[PluginState[D, NP], DispatchResult]:
    return st.transform_s(_.data, lambda r, s: r.copy(data=s))


# FIXME need to transform state here to use AutoData, not PluginState, for send_message1
@do(NvimIOState[PluginState[D, NP], DispatchResult])
def send_message(msg: M, prio: float=None) -> Generator:
    yield NvimIOState.modify(__.log_message(msg.msg))
    components = yield NvimIOState.inspect(_.components)
    yield transform_data_state(send_message1(components, msg, prio))


__all__ = ('send_message',)
