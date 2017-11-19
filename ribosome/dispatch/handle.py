from typing import TypeVar, Type, Callable, Any, Tuple, Generic

from neovim.msgpack_rpc.event_loop.base import BaseEventLoop

import amino
from amino import _, L, __
from amino.do import do, Do
from amino.dispatch import dispatch_alg
from amino.util.exception import format_exception
from amino.algebra import Algebra

from ribosome.nvim import NvimFacade, NvimIO
from ribosome.logging import ribo_log
from ribosome import NvimPlugin
from ribosome.config import Config
from ribosome.machine.process_messages import PrioQueue
from ribosome.machine.message_base import Message
from ribosome.machine.loop import process_message
from ribosome.machine.transition import TransitionResult
from ribosome.machine.send_message import send_message
from ribosome.nvim.io import NvimIOState
from ribosome.dispatch.run import DispatchJob, RunDispatchSync, RunDispatchAsync, invalid_dispatch
from ribosome.dispatch.data import (DispatchError, DispatchReturn, DispatchUnit, DispatchOutput, DispatchSync,
                                            DispatchAsync, DispatchResult, Dispatch, DispatchIO, IODIO, DIO,
                                            DispatchErrors)
from ribosome.plugin_state import PluginState, PluginStateHolder

Loop = TypeVar('Loop', bound=BaseEventLoop)
NP = TypeVar('NP', bound=NvimPlugin)
D = TypeVar('D')
AS = TypeVar('AS')
A = TypeVar('A', bound=AS)
B = TypeVar('B')
C = TypeVar('C', bound=Config)
R = TypeVar('R')
DP = TypeVar('DP', bound=Dispatch)
RDP = TypeVar('RDP', bound=Algebra)
Res = NvimIOState[PluginState[D, NP], DispatchResult]


class ExecuteDispatchIO:

    def i_o_dio(self, io: IODIO[A]) -> NvimIO[Any]:
        return


execute_io = dispatch_alg(ExecuteDispatchIO(), DIO, '')


class ExecuteDispatchOutput:

    def dispatch_error(self, result: DispatchError) -> NvimIOState[PluginState[D, NP], R]:
        return NvimIOState.lift(result.exception / NvimIO.exception | NvimIO(lambda v: ribo_log.error(result.message)))

    def dispatch_errors(self, result: DispatchErrors) -> NvimIOState[PluginState[D, NP], R]:
        return result.errors.traverse(self.dispatch_error, NvimIOState)

    def dispatch_return(self, result: DispatchReturn) -> NvimIOState[PluginState[D, NP], R]:
        return NvimIOState.pure(result.value)

    def dispatch_unit(self, result: DispatchUnit) -> NvimIOState[PluginState[D, NP], R]:
        return NvimIOState.pure(0)

    def dispatch_io(self, result: DispatchIO) -> NvimIOState[PluginState[D, NP], R]:
        return execute_io(result)


execute_output = dispatch_alg(ExecuteDispatchOutput(), DispatchOutput, '')


@do(NvimIOState[PluginState[D, NP], R])
def run_dispatch(action: Callable[[], NvimIOState[PluginState[D, NP], B]], unpack: Callable[[B], Res]) -> Do:
    response = yield action()
    result = yield unpack(response)
    yield NvimIOState.modify(__.enqueue(result.msgs))
    yield execute_output(result.output)


# FIXME check how long-running messages can be handled; timeout for acquire is 10s
def exclusive(holder: PluginStateHolder, f: Callable[[], NvimIO[R]]) -> NvimIO[R]:
    def release(error: Any) -> None:
        holder.release()
    yield NvimIO(lambda v: holder.acquire())
    state, response = yield f().error_effect(release)
    yield NvimIO(lambda v: holder.update(state))
    yield NvimIO(release)
    yield NvimIO.pure(response)


@do(NvimIO[R])
def exclusive_dispatch(holder: PluginStateHolder,
                       action: Callable[[], NvimIOState[PluginState[D, NP], B]],
                       unpack: Callable[[B], NvimIOState[PluginState[D, NP], DispatchResult]]) -> Do:
    return exclusive(holder, lambda: run_dispatch(action, unpack).run(holder.state))


class DispatchRunner(Generic[RDP]):

    @staticmethod
    def cons(run: Type[RDP], dp: Type[DP]) -> 'DispatchRunner[RDP]':
        return DispatchRunner(lambda args: dispatch_alg(run(args), dp, '', invalid_dispatch))

    def __init__(self, f: Callable[[tuple], Callable[[RDP], NvimIOState[PluginState[D, NP], DispatchOutput]]]) -> None:
        self.f = f

    def __call__(self, args: tuple) -> Callable[[RDP], NvimIOState[PluginState[D, NP], DispatchOutput]]:
        return self.f(args)


sync_runner = DispatchRunner.cons(RunDispatchSync, DispatchSync)
async_runner = DispatchRunner.cons(RunDispatchAsync, DispatchAsync)


def sync_sender(job: DispatchJob, dispatch: DP, runner: DispatchRunner[RDP]) -> Callable[[], Res]:
    def send() -> NvimIOState[PluginState[D, NP], DispatchResult]:
        return runner(job.args)(dispatch)
    return send


def execute(job: DispatchJob, dispatch: DP, runner: DispatchRunner[RDP]) -> NvimIO[Any]:
    return exclusive_dispatch(job.state, sync_sender(job, dispatch, runner), NvimIOState.pure)


# unconditionally fork a resend loop in case the sync transition has returned messages
# only allow the first transition to provide a return value
def execute_sync(job: DispatchJob, dispatch: DispatchSync) -> NvimIO[Any]:
    return execute(job, dispatch, sync_runner)


def request_error(job: DispatchJob, exc: Exception) -> int:
    sync_prefix = '' if job.sync else 'a'
    desc = f'{sync_prefix}sync request {job.name}({job.args}) to `{job.plugin_name}`'
    tb = format_exception(exc).join_lines
    ribo_log.error(f'fatal error in {desc}')
    exc_logger = ribo_log.error if amino.development else ribo_log.debug
    exc_logger(f'{desc} failed:\n{tb}')
    return 1


def resend_send() -> NvimIOState[PluginState[D, NP], Tuple[PrioQueue[Message], TransitionResult]]:
    return NvimIOState.inspect(lambda state: process_message(state.messages, send_message))


@do(NvimIOState[PluginState[D, NP], Tuple[PrioQueue[Message], TransitionResult]])
def resend_unpack(result: Tuple[PrioQueue[Message], TransitionResult]) -> Do:
    messages, trs = result
    yield NvimIOState.modify(__.copy(messages=messages))
    yield trs


# maybe don't enqueue messages here, but in `execute_output`
@do(NvimIO[PluginState[D, NP]])
def resend_loop(holder: PluginStateHolder) -> Do:
    yield exclusive_dispatch(holder, resend_send, resend_unpack)
    yield resend_loop(holder) if holder.has_messages else NvimIO.pure(holder.state)


@do(NvimIO[Any])
def execute_async_loop(job: DispatchJob, dispatch: DispatchAsync) -> Do:
    yield execute(job, dispatch, async_runner)
    yield resend_loop(job.state)


def execute_async(job: DispatchJob, dispatch: DispatchAsync) -> NvimIO[None]:
    def run(vim: NvimFacade) -> None:
        execute_async_loop(job, dispatch).attempt(vim).lmap(L(request_error)(job, _))
    return NvimIO.fork(run)


@do(NvimIO[Any])
def execute_dispatch_job(job: DispatchJob) -> Do:
    dispatch = yield NvimIO.from_maybe(job.dispatches.lift(job.name), 'no handler')
    relay = execute_sync if dispatch.sync else execute_async
    yield relay(job, dispatch)


__all__ = ('execute_dispatch_job', 'execute_async_loop', 'execute_sync', 'execute')
