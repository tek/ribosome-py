import time
from typing import TypeVar, Callable, Generator

from amino import __, Maybe, Boolean, _, L
from amino.state import EvalState
from amino.do import tdo

from ribosome.machine.transition import TransitionResult
from ribosome.machine.base import TransState
from ribosome.request.dispatch import PluginState, ComponentState
from ribosome.machine.message_base import Message, Sendable, Envelope
from ribosome.logging import ribo_log
from ribosome.machine.handler import HandlerJob

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


def internal(data: D, msg: Message) -> TransState:
    return EvalState.pure(TransitionResult.unhandled(data))


def format_report(self, msg: Message, dur: float, name: str) -> str:
    return '{} took {:.4f}s for {} to process'.format(msg, dur, name)


def check_time(start_time: int, msg: Message, name: str) -> None:
    dur = time.time() - start_time
    ribo_log.debug1(format_report, msg, dur, name)
    # if dur > self._min_report_time:
    #     self._reports = self._reports.cat((msg, dur))


def process(component: ComponentState, data: D, msg: Message, prio: float=None) -> TransState:
    def execute(handler: Callable) -> TransitionResult:
        ribo_log.debug(f'handling {msg} in {component.name}')
        job = HandlerJob.from_handler(component.name, handler, data, msg)
        result = job.run()
        check_time(job.start_time, msg, component.name)
        return EvalState.pure(result)
    return resolve_handler(component, msg, prio) / execute | (lambda: internal(data, msg))


@tdo(TransState)
def send_message_to_component(component: ComponentState, data: D, msg: M, prio: float=None) -> TransState:
    result = yield process(component, data, msg, prio)
    log = yield EvalState.get()
    resend = result.resend
    new_log, next_msg = log.resend(resend).pop
    yield EvalState.set(new_log)
    yield EvalState.pure(result)


def send_to(msg: Message, prio: float=None) -> Callable[[TransState, ComponentState], TransState]:
    @tdo(TransState)
    def send(z: TransState, comp: ComponentState) -> Generator:
        current = yield z
        next = yield send_message_to_component(comp, current.data, msg, prio)
        yield EvalState.pure(current.accum(next))
    return send


def send_msg(state: PluginState[D, NP], z: TransState, msg: Message, prio: float=None) -> TransState:
    return state.components.fold_left(z)(send_to(msg, prio))


def send_envelope(state: PluginState[D, NP], z: TransState, env: Envelope, prio: float=None) -> TransState:
    msg = env.msg
    def to_comp(name: str) -> TransState:
        return state.component(name) / L(send_to(msg, prio))(z, _) | z
    return env.recipient / to_comp | (lambda: send_msg(state, z, msg, prio))


@tdo(TransState)
def send_message(state: PluginState[D, NP], msg: M, prio: float=None) -> Generator:
    ''' send **msg** to all submachines, passing the transformed data from each machine to the next and
    accumulating published messages.
    '''
    yield EvalState.modify(__.log(msg.msg))
    send = Boolean.isinstance(msg, Envelope).cata(send_envelope, send_msg)
    yield send(state, EvalState.pure(TransitionResult.unhandled(state.data)), msg, prio)


__all__ = ('send_message',)
