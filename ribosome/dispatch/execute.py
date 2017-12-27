from typing import TypeVar, Type, Callable, Any, Tuple, Generic
from concurrent.futures import wait, ThreadPoolExecutor

from neovim.msgpack_rpc.event_loop.base import BaseEventLoop

from amino import _, __, Try, IO, Lists, Either, List, L, Nil
from amino.do import do, Do
from amino.dispatch import dispatch_alg
from amino.util.exception import format_exception
from amino.algebra import Algebra
from amino.io import IOException

from ribosome.nvim import NvimFacade, NvimIO
from ribosome.logging import ribo_log, Logging
from ribosome.config import Config
from ribosome.nvim.io import NS, NResult, NSuccess, NError, NFatal
from ribosome.dispatch.run import (DispatchJob, RunDispatchSync, RunDispatchAsync, invalid_dispatch, execute_data_trans,
                                   log_trans)
from ribosome.dispatch.data import (DispatchError, DispatchReturn, DispatchUnit, DispatchOutput, DispatchSync,
                                    DispatchAsync, DispatchResult, Dispatch, DispatchIO, IODIO, DIO, DispatchErrors,
                                    NvimIODIO, DispatchOutputAggregate, GatherIOsDIO, DispatchDo, GatherSubprocsDIO,
                                    DispatchLog)
from ribosome.plugin_state import PluginState, PluginStateHolder, DispatchAffiliaton
from ribosome.trans.queue import PrioQueue
from ribosome.trans.message_base import Message
from ribosome.dispatch.loop import process_message
from ribosome.trans.send_message import send_message
from ribosome.dispatch.transform import validate_trans_complete
from ribosome.trans.action import TransM, TransMPure, TransMBind, LogMessage, Info, Error
from ribosome.trans.handler import TransComplete

Loop = TypeVar('Loop', bound=BaseEventLoop)
D = TypeVar('D')
AS = TypeVar('AS')
A = TypeVar('A', bound=AS)
B = TypeVar('B')
C = TypeVar('C', bound=Config)
R = TypeVar('R')
DP = TypeVar('DP', bound=Dispatch)
RDP = TypeVar('RDP', bound=Algebra)
Res = NS[PluginState[D], DispatchResult]


def gather_ios(ios: List[IO[A]], timeout: float) -> List[Either[IOException, A]]:
    with ThreadPoolExecutor(thread_name_prefix='ribosome_dio') as executor:
        ribo_log.debug(f'executing ios {ios}')
        futures = ios.map(lambda i: executor.submit(i.attempt_run))
        completed, timed_out = wait(futures, timeout=timeout)
        ribo_log.debug(f'completed ios {completed}')
        if timed_out:
            ribo_log.debug(f'ios timed out: {timed_out}')
        return Lists.wrap(completed).map(__.result(timeout=timeout))


class ExecuteDispatchIO(Logging):

    def iodio(self, io: IODIO[A]) -> NS[PluginState[D], TransComplete]:
        return NS.from_io(io.io)

    def gather_i_os_dio(self, io: GatherIOsDIO[A]) -> NS[PluginState[D], TransComplete]:
        def gather() -> R:
            gio = io.io
            return gio.handle_result(gather_ios(gio.ios, gio.timeout))
        return NS.from_io(IO.delay(gather))

    def gather_subprocs_dio(self, io: GatherSubprocsDIO[A, TransComplete]) -> NS[PluginState[D], TransComplete]:
        ribo_log.debug(f'gathering {io}')
        def gather() -> TransComplete:
            gio = io.io
            popens = gio.procs.map(__.execute(gio.timeout))
            return gio.handle_result(gather_ios(popens, gio.timeout))
        return NS.from_io(IO.delay(gather))

    def nvim_iodio(self, io: NvimIODIO[A]) -> NS[PluginState[D], TransComplete]:
        return NS.lift(io.io)


execute_io = dispatch_alg(ExecuteDispatchIO(), DIO, '')


@do(NS[PluginState[D], R])
def run_trans_m(tr: TransM) -> Do:
    if isinstance(tr, TransMPure):
        yield log_trans(tr.handler)
        result = yield execute_data_trans(tr.handler)
        yield normalize_output(result)
    elif isinstance(tr, TransMBind):
        result = yield run_trans_m(tr.fa)
        n = tr.f(result)
        yield run_trans_m(n)


class DispatchLogger:

    def info(self, msg: Info) -> NS[D, None]:
        return NS.delay(lambda v: ribo_log.info(msg.message))

    def error(self, msg: Error) -> NS[D, None]:
        return NS.delay(lambda v: ribo_log.error(msg))


dispatch_log = dispatch_alg(DispatchLogger(), LogMessage)


class ExecuteDispatchOutput(Logging):

    def dispatch_error(self, result: DispatchError) -> NS[PluginState[D], R]:
        io = result.exception / NvimIO.exception | NvimIO.delay(lambda v: ribo_log.error(result.message))
        return NS.lift(io)

    def dispatch_errors(self, result: DispatchErrors) -> NS[PluginState[D], R]:
        return result.errors.traverse(self.dispatch_error, NS)

    def dispatch_return(self, result: DispatchReturn) -> NS[PluginState[D], R]:
        return NS.pure(result.value)

    def dispatch_unit(self, result: DispatchUnit) -> NS[PluginState[D], R]:
        return NS.pure(0)

    @do(NS[PluginState[D], R])
    def dispatch_io(self, result: DispatchIO) -> Do:
        custom_executor = yield NS.inspect(_.dispatch_config.io_executor)
        executor = custom_executor | (lambda: execute_io)
        inner = yield executor(result.io)
        result = yield validate_trans_complete(TransComplete('io', inner))
        yield normalize_output(result)

    @do(NS[PluginState[D], R])
    def dispatch_output_aggregate(self, result: DispatchOutputAggregate) -> Do:
        yield result.results.traverse(normalize_output, NS)
        yield DispatchResult.unit_nio

    def dispatch_do(self, result: DispatchDo) -> NS[PluginState[D], R]:
        return run_trans_m(result.trans.action)

    @do(NS[PluginState[D], R])
    def dispatch_log(self, result: DispatchLog) -> Do:
        custom_logger = yield NS.inspect(_.logger)
        logger = custom_logger | (lambda: dispatch_log)
        yield logger(result.trans)


execute_output = dispatch_alg(ExecuteDispatchOutput(), DispatchOutput, '')


@do(NS[PluginState[D], R])
def normalize_output(result: DispatchResult) -> Do:
    yield NS.modify(__.enqueue(result.msgs))
    yield execute_output(result.output)


@do(NS[PluginState[D], R])
def run_dispatch(action: Callable[[], NS[PluginState[D], B]], unpack: Callable[[B], Res]) -> Do:
    response = yield action()
    result = yield unpack(response)
    yield normalize_output(result)


def exclusive(holder: PluginStateHolder, f: Callable[[], NvimIO[R]], desc: str) -> NvimIO[R]:
    yield holder.acquire()
    ribo_log.debug(f'exclusive: {desc}')
    state, response = yield f().error_effect_f(holder.release)
    yield NvimIO.delay(lambda v: holder.update(state))
    yield holder.release()
    ribo_log.debug(f'release: {desc}')
    yield NvimIO.pure(response)


@do(NvimIO[R])
def exclusive_dispatch(holder: PluginStateHolder,
                       action: Callable[[], NS[PluginState[D], B]],
                       unpack: Callable[[B], NS[PluginState[D], DispatchResult]],
                       desc: str) -> Do:
    return exclusive(holder, lambda: run_dispatch(action, unpack).run(holder.state), desc)


class DispatchRunner(Generic[RDP]):

    @staticmethod
    def cons(run: Type[RDP], dp: Type[DP]) -> 'DispatchRunner[RDP]':
        return DispatchRunner(lambda args: dispatch_alg(run(args), dp, '', L(invalid_dispatch)(run, _)))

    def __init__(self, f: Callable[[tuple], Callable[[RDP], NS[PluginState[D], DispatchOutput]]]) -> None:
        self.f = f

    def __call__(self, args: List[Any]) -> Callable[[RDP], NS[PluginState[D], DispatchOutput]]:
        return self.f(args)


sync_runner = DispatchRunner.cons(RunDispatchSync, DispatchSync)
async_runner = DispatchRunner.cons(RunDispatchAsync, DispatchAsync)


def sync_sender(args: List[Any], aff: DispatchAffiliaton[DP], runner: DispatchRunner[RDP]) -> Callable[[], Res]:
    def send() -> NS[PluginState[D], DispatchResult]:
        return runner(args)(aff.dispatch, aff)
    return send


def async_sender(args: List[Any],
                 dispatches: List[DispatchAffiliaton[DP]],
                 runner: DispatchRunner[RDP]) -> Callable[[], Res]:
    def send() -> NS[PluginState[D], DispatchResult]:
        r = runner(args)
        return (
            dispatches.traverse(lambda a: r(a.dispatch, a), NS) /
            DispatchOutputAggregate /
            L(DispatchResult)(_, Nil)
        )
    return send


def execute(state: PluginStateHolder[D],
            args: List[Any],
            dispatch: DispatchAffiliaton[DP],
            runner: DispatchRunner[RDP]) -> NvimIO[Any]:
    return exclusive_dispatch(state, sync_sender(args, dispatch, runner), NS.pure, dispatch.desc)


def run_forked_job(vim: NvimFacade, f: Callable[[], NvimIO[None]], job: DispatchJob) -> None:
    request_result(job, Try(f).value_or(NvimIO.exception).result(vim))
    ribo_log.debug(f'async job {job.name} completed')


def sync_dispatch(job: DispatchRunner) -> Either[str, DispatchSync]:
    name = job.name
    return job.state.state.dispatch_config.sync_dispatch.lift(name).to_either(f'no sync dispatch for {name}')


def async_dispatches(job: DispatchRunner) -> Either[str, List[DispatchAsync]]:
    name = job.name
    return job.state.state.dispatch_config.async_dispatch.lift(name).to_either(f'no sync dispatch for {name}')


@do(NvimIO)
def execute_sync(job: DispatchJob) -> Do:
    dispatch = yield NvimIO.from_either(sync_dispatch(job))
    response = yield execute(job.state, job.args, dispatch, sync_runner)
    yield NvimIO.pure(response)


class RequestResult:

    @property
    def sync_prefix(self) -> str:
        return '' if self.job.sync else 'a'

    @property
    def desc(self) -> str:
        return f'{self.sync_prefix}sync request {self.job.name}({self.job.args}) to `{self.job.plugin_name}`'

    def __init__(self, job: DispatchJob) -> None:
        self.job = job

    def n_success(self, result: NSuccess) -> Any:
        return result.value

    def n_error(self, result: NError) -> Any:
        ribo_log.error(result.error)
        return 1

    def n_fatal(self, result: NFatal) -> Any:
        exc = result.exception
        tb = format_exception(exc).join_lines
        desc = self.desc
        ribo_log.error(f'fatal error in {desc}')
        ribo_log.debug(f'{desc} failed:\n{tb}')
        return 2


def request_result(job: DispatchJob, result: NResult) -> int:
    handler: Callable[[NResult], Any] = dispatch_alg(RequestResult(job), NResult)
    return handler(result)


def resend_send() -> NS[PluginState[D], Tuple[PrioQueue[Message], DispatchResult]]:
    return NS.inspect(lambda state: process_message(state.messages, send_message))


@do(NS[PluginState[D], DispatchResult])
def resend_unpack(result: Tuple[PrioQueue[Message], DispatchResult]) -> Do:
    messages, trs = result
    yield NS.modify(__.copy(messages=messages))
    yield trs


@do(NvimIO[PluginState[D]])
def resend_loop(holder: PluginStateHolder) -> Do:
    @do(NvimIO[PluginState[D]])
    def loop() -> Do:
        messages = holder.messages.join_comma
        yield exclusive_dispatch(holder, resend_send, resend_unpack, f'resend {messages}')
        yield resend_loop(holder)
    yield loop() if holder.has_messages else NvimIO.pure(holder.state)


@do(NvimIO[PluginState[D]])
def execute_async_loop(job: DispatchJob, dispatches: List[DispatchAsync]) -> Do:
    yield dispatches.traverse(L(execute)(job.state, job.args, _, async_runner), NvimIO)
    yield resend_loop(job.state)


@do(NvimIO)
def execute_async(job: DispatchJob) -> NvimIO[None]:
    dispatches = yield NvimIO.from_either(async_dispatches(job))
    result = yield Try(execute_async_loop, job, dispatches).value_or(NvimIO.exception)
    ribo_log.debug(f'async job {job.name} completed')
    yield NvimIO.from_io(job.state.dispatch_complete())
    yield NvimIO.pure(result)


@do(NvimIO[Any])
def execute_dispatch_job(job: DispatchJob) -> Do:
    relay = execute_sync if job.sync else execute_async
    yield relay(job)


__all__ = ('execute_dispatch_job', 'execute_async_loop', 'execute_sync', 'execute')
