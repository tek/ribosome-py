from typing import TypeVar, Callable, Any, Tuple
from concurrent.futures import wait, ThreadPoolExecutor

from neovim.msgpack_rpc.event_loop.base import BaseEventLoop

from amino import _, __, IO, Lists, Either, List, L, Nil
from amino.do import do, Do
from amino.dispatch import PatMat
from amino.util.exception import format_exception
from amino.io import IOException
from amino.string.hues import red, blue, green
from amino.util.string import decode

from ribosome.nvim import NvimIO, NvimFacade
from ribosome.logging import ribo_log
from ribosome.config.config import Config
from ribosome.nvim.io import NS, NResult, NSuccess, NError, NFatal
from ribosome.dispatch.run import (DispatchJob, log_trans, DispatchState, run_trans, plugin_to_dispatch,
                                   setup_and_run_trans)
from ribosome.dispatch.data import (DispatchError, DispatchReturn, DispatchUnit, DispatchOutput,
                                    DispatchAsync, Dispatch, DispatchIO, IODIO, DIO, DispatchErrors, NvimIODIO,
                                    DispatchOutputAggregate, GatherIOsDIO, DispatchDo, GatherSubprocsDIO, DispatchLog)
from ribosome.plugin_state import PluginState, PluginStateHolder, DispatchAffiliation, AffiliatedDispatch
from ribosome.trans.action import LogMessage, Info, Error
from ribosome.trans.handler import TransF, Trans, TransMBind, TransMPure
from ribosome.config.settings import Settings
from ribosome.trans.run import TransComplete

Loop = TypeVar('Loop', bound=BaseEventLoop)
D = TypeVar('D')
AS = TypeVar('AS')
A = TypeVar('A', bound=AS)
B = TypeVar('B')
C = TypeVar('C', bound=Config)
R = TypeVar('R')
DP = TypeVar('DP', bound=Dispatch)
RDP = TypeVar('RDP')
S = TypeVar('S', bound=Settings)
CC = TypeVar('CC')
Res = NS[PluginState[S, D, CC], DispatchOutput]
DRes = NS[DispatchState[S, D, CC], DispatchOutput]


def gather_ios(ios: List[IO[A]], timeout: float) -> List[Either[IOException, A]]:
    with ThreadPoolExecutor(thread_name_prefix='ribosome_dio') as executor:
        ribo_log.debug(f'executing ios {ios}')
        futures = ios.map(lambda i: executor.submit(i.attempt_run))
        completed, timed_out = wait(futures, timeout=timeout)
        ribo_log.debug(f'completed ios {completed}')
        if timed_out:
            ribo_log.debug(f'ios timed out: {timed_out}')
        return Lists.wrap(completed).map(__.result(timeout=timeout))


class execute_io(PatMat, alg=DIO):

    def iodio(self, io: IODIO[A]) -> NS[PluginState[S, D, CC], TransComplete]:
        return NS.from_io(io.io)

    def gather_i_os_dio(self, io: GatherIOsDIO[A]) -> NS[PluginState[S, D, CC], TransComplete]:
        def gather() -> R:
            gio = io.io
            return gather_ios(gio.ios, gio.timeout)
        return NS.from_io(IO.delay(gather))

    def gather_subprocs_dio(self, io: GatherSubprocsDIO[A, TransComplete]) -> NS[PluginState[S, D, CC], TransComplete]:
        ribo_log.debug(f'gathering {io}')
        def gather() -> TransComplete:
            gio = io.io
            popens = gio.procs.map(__.execute(gio.timeout))
            return gather_ios(popens, gio.timeout)
        return NS.from_io(IO.delay(gather))

    def nvim_iodio(self, io: NvimIODIO[A]) -> NS[PluginState[S, D, CC], TransComplete]:
        return NS.lift(io.io)


@do(NS[DispatchState[S, D, CC], R])
def run_trans_m_trans(handler: TransF, aff: DispatchAffiliation) -> Do:
    yield plugin_to_dispatch(log_trans(handler))
    result = yield run_trans(aff, handler, Nil)
    yield execute_dispatch_output.match(result)


# TODO determine affiliation from the type in the handler's state
@do(NS[DispatchState[S, D, CC], R])
def run_trans_m(tr: Trans) -> Do:
    if isinstance(tr, TransF):
        current = yield NS.inspect(_.aff)
        aff = yield NS.inspect(__.state.reaffiliate(tr, current))
        if current != aff:
            from_name = red(current.name)
            to_name = green(aff.name)
            ribo_log.debug(f'switching dispatch affiliation for {blue(tr.name)}: {from_name} -> {to_name}')
        yield NS.modify(__.set.aff(aff))
        result = yield run_trans_m_trans(tr, aff)
        yield NS.modify(__.set.aff(current))
        yield NS.pure(result)
    elif isinstance(tr, TransMBind):
        result = yield run_trans_m(tr.fa)
        next_trans = tr.f(result)
        yield run_trans_m(next_trans)
    elif isinstance(tr, TransMPure):
        yield NS.pure(tr.value)


class dispatch_log(PatMat, alg=LogMessage):

    def info(self, msg: Info) -> NS[D, None]:
        return NS.delay(lambda v: ribo_log.info(msg.message))

    def error(self, msg: Error) -> NS[D, None]:
        return NS.delay(lambda v: ribo_log.error(msg))


class execute_dispatch_output(PatMat, alg=DispatchOutput):

    def dispatch_error(self, result: DispatchError) -> NS[DispatchState[S, D, CC], R]:
        io = result.exception / NvimIO.exception | NvimIO.error(result.message)
        return NS.lift(io)

    def dispatch_errors(self, result: DispatchErrors) -> NS[DispatchState[S, D, CC], R]:
        return result.errors.traverse(self.dispatch_error, NS)

    def dispatch_return(self, result: DispatchReturn) -> NS[DispatchState[S, D, CC], R]:
        return NS.pure(result.value)

    def dispatch_unit(self, result: DispatchUnit) -> NS[DispatchState[S, D, CC], R]:
        return NS.pure(0)

    @do(NS[DispatchState[S, D, CC], R])
    def dispatch_io(self, result: DispatchIO) -> Do:
        custom_executor = yield NS.inspect(_.state.dispatch_config.io_executor)
        executor = custom_executor | (lambda: execute_io.match)
        io_result = yield executor(result.io)
        yield run_trans_m(result.io.handle_result(io_result))

    @do(NS[DispatchState[S, D, CC], R])
    def dispatch_output_aggregate(self, result: DispatchOutputAggregate) -> Do:
        yield result.results.traverse(execute_dispatch_output.match, NS)

    @do(NS[DispatchState[S, D, CC], R])
    def dispatch_do(self, result: DispatchDo) -> Do:
        yield run_trans_m(result.trans.action)

    @do(NS[DispatchState[S, D, CC], R])
    def dispatch_log(self, result: DispatchLog) -> Do:
        custom_logger = yield NS.inspect(_.state.logger)
        logger = custom_logger | (lambda: dispatch_log.match)
        yield logger(result.trans)


@do(NS[DispatchState[S, D, CC], R])
def compute_dispatch(dispatch: AffiliatedDispatch[DP], args: List[Any]) -> Do:
    result = yield setup_and_run_trans(dispatch.dispatch, dispatch.aff, args)
    yield execute_dispatch_output.match(result)


@do(Res)
def compute_dispatches(dispatches: List[AffiliatedDispatch[DP]], args: List[Any]) -> Do:
    output = yield dispatches.traverse(lambda a: setup_and_run_trans(a.dispatch, a.aff, args), NS)
    yield execute_dispatch_output.match(DispatchOutputAggregate(output))


def exclusive(holder: PluginStateHolder, f: Callable[[], NvimIO[Tuple[DispatchState, R]]], desc: str) -> NvimIO[R]:
    yield holder.acquire()
    ribo_log.debug2(f'exclusive: {desc}')
    state, response = yield f().error_effect_f(holder.release)
    yield NvimIO.delay(lambda v: holder.update(state.state))
    yield holder.release()
    ribo_log.debug2(f'release: {desc}')
    yield NvimIO.pure(response)


@do(NvimIO[R])
def exclusive_dispatch(holder: PluginStateHolder,
                       dispatch: AffiliatedDispatch[DP],
                       args: List[Any],
                       desc: str,
                       aff: DispatchAffiliation) -> Do:
    return exclusive(holder, lambda: compute_dispatch(dispatch, args).run(DispatchState(holder.state, aff)), desc)


def execute(state: PluginStateHolder[D], dispatch: AffiliatedDispatch[DP], args: List[Any]) -> NvimIO[Any]:
    return exclusive_dispatch(state, dispatch, args, dispatch.desc, dispatch.aff)


def job_dispatches(job: DispatchJob) -> Either[str, List[AffiliatedDispatch[DispatchAsync]]]:
    name = job.name
    return job.state.state.dispatch_config.dispatches.lift(name).to_either(f'no sync dispatch for {name}')


@do(NvimIO[List[Any]])
def execute_dispatch_job(job: DispatchJob) -> Do:
    dispatches = yield NvimIO.from_either(job_dispatches(job))
    result = yield dispatches.traverse(L(execute)(job.state, _, job.args), NvimIO)
    ribo_log.debug(f'async job {job.name} completed')
    yield NvimIO.from_io(job.state.dispatch_complete())
    yield NvimIO.pure(result)


class request_result(PatMat, alg=NResult):

    def __init__(self, job: DispatchJob) -> None:
        self.job = job

    def n_success(self, result: NSuccess[List[Any]]) -> Any:
        desc = self.job.desc
        def multiple_results() -> int:
            ribo_log.error(f'multiple request handlers for {desc}')
            return 4
        def sync_result(head: Any, tail: List[Any]) -> Any:
            return head if tail.empty else multiple_results()
        def empty_result() -> int:
            ribo_log.error(f'no result in {desc}')
            return 3
        return result.value.detach_head.map2(sync_result) | empty_result if self.job.sync else 0

    def n_error(self, result: NError[List[Any]]) -> Any:
        ribo_log.error(result.error)
        return 1

    def n_fatal(self, result: NFatal[List[Any]]) -> Any:
        exc = result.exception
        tb = format_exception(exc).join_lines
        desc = self.job.desc
        ribo_log.error(f'fatal error in {desc}')
        ribo_log.debug(f'{desc} failed:\n{tb}')
        return 2


def dispatch_job(state: PluginStateHolder[D], name: str, args: tuple, sync: bool) -> DispatchJob:
    decoded_args = decode(args)
    fun_args = decoded_args.head | Nil
    bang = decoded_args.lift(1).contains(1)
    return DispatchJob(state, decode(name), fun_args, sync, bang)


def execute_request(vim: NvimFacade, state: PluginStateHolder[D], name: str, args: tuple, sync: bool) -> Any:
    sync_prefix = '' if sync else 'a'
    job = dispatch_job(state, name, args, sync)
    ribo_log.debug(f'dispatching {sync_prefix}sync request: {job.name}({job.args})')
    result = request_result(job)(execute_dispatch_job(job).result(vim))
    if sync:
        ribo_log.debug(f'request `{job.name}` completed: {result}')
    return vim.encode_vim_data(result)


__all__ = ('execute_dispatch_job', 'execute', 'compute_dispatches', 'compute_dispatch')
