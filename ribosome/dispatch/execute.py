from typing import TypeVar, Callable, Any, Tuple
from concurrent.futures import wait, ThreadPoolExecutor

from neovim.msgpack_rpc.event_loop.base import BaseEventLoop

from amino import _, __, IO, Lists, Either, List, L, Nil
from amino.do import do, Do
from amino.case import Case
from amino.util.exception import format_exception
from amino.io import IOException
from amino.util.string import decode
from amino.state import EitherState

from ribosome.nvim.io.compute import NvimIO
from ribosome.logging import ribo_log
from ribosome.config.config import Config
from ribosome.nvim.io.state import NS
from ribosome.data.plugin_state import PluginState
# from ribosome.trans.action import LogMessage, Info, Error
from ribosome.compute.prog import Program
from ribosome.config.settings import Settings
from ribosome import NvimApi
from ribosome.nvim.io.data import NResult, NSuccess, NError, NFatal
from ribosome.nvim.io.api import N
from ribosome.dispatch.job import DispatchJob
from ribosome.request.handler.handler import RequestHandler
from ribosome.request.args import ParamsSpec
from ribosome.request.handler.arg_parser import ArgParser, JsonArgParser, TokenArgParser
from ribosome.compute.run import run_prog
from ribosome.data.plugin_state_holder import PluginStateHolder

Loop = TypeVar('Loop', bound=BaseEventLoop)
D = TypeVar('D')
A = TypeVar('A')
B = TypeVar('B')
C = TypeVar('C', bound=Config)
R = TypeVar('R')
RDP = TypeVar('RDP')
S = TypeVar('S', bound=Settings)
CC = TypeVar('CC')


def gather_ios(ios: List[IO[A]], timeout: float) -> List[Either[IOException, A]]:
    with ThreadPoolExecutor(thread_name_prefix='ribosome_dio') as executor:
        ribo_log.debug(f'executing ios {ios}')
        futures = ios.map(lambda i: executor.submit(i.attempt_run))
        completed, timed_out = wait(futures, timeout=timeout)
        ribo_log.debug(f'completed ios {completed}')
        if timed_out:
            ribo_log.debug(f'ios timed out: {timed_out}')
        return Lists.wrap(completed).map(__.result(timeout=timeout))


# class execute_io(Case, alg=DIO):

#     def iodio(self, io: IODIO[A]) -> NS[PluginState[S, D, CC], TransComplete]:
#         return NS.from_io(io.io)

#     def gather_i_os_dio(self, io: GatherIOsDIO[A]) -> NS[PluginState[S, D, CC], TransComplete]:
#         def gather() -> R:
#             gio = io.io
#             return gather_ios(gio.ios, gio.timeout)
#         return NS.from_io(IO.delay(gather))

#     def gather_subprocs_dio(self, io: GatherSubprocsDIO[A, TransComplete]) -> NS[PluginState[S, D, CC], TransComplete]:
#         ribo_log.debug(f'gathering {io}')
#         def gather() -> TransComplete:
#             gio = io.io
#             popens = gio.procs.map(__.execute(gio.timeout))
#             return gather_ios(popens, gio.timeout)
#         return NS.from_io(IO.delay(gather))

#     def nvim_iodio(self, io: NvimIODIO[A]) -> NS[PluginState[S, D, CC], TransComplete]:
#         return NS.lift(io.io)


@do(NS[PluginState[S, D, CC], R])
def run_trans_f(handler: Program) -> Do:
    yield plugin_to_dispatch(log_trans(handler))
    result = yield run_program(aff, handler, Nil)
    yield execute_dispatch_output.match(result)


# class dispatch_log(Case, alg=LogMessage):

#     def info(self, msg: Info) -> NS[D, None]:
#         return NS.delay(lambda v: ribo_log.info(msg.message))

#     def error(self, msg: Error) -> NS[D, None]:
#         return NS.delay(lambda v: ribo_log.error(msg))


# class execute_dispatch_output(Case, alg=DispatchOutput):

#     def dispatch_error(self, result: DispatchError) -> NS[PluginState[S, D, CC], R]:
#         io = result.exception / N.exception | N.error(result.message)
#         return NS.lift(io)

#     def dispatch_errors(self, result: DispatchErrors) -> NS[PluginState[S, D, CC], R]:
#         return result.errors.traverse(self.dispatch_error, NS)

#     def dispatch_return(self, result: DispatchReturn) -> NS[PluginState[S, D, CC], R]:
#         return NS.pure(result.value)

#     def dispatch_unit(self, result: DispatchUnit) -> NS[PluginState[S, D, CC], R]:
#         return NS.pure(0)

#     @do(NS[PluginState[S, D, CC], R])
#     def dispatch_io(self, result: DispatchIO) -> Do:
#         custom_executor = yield NS.inspect(_.state.io_executor)
#         executor = custom_executor | (lambda: execute_io.match)
#         io_result = yield executor(result.io)
#         yield eval_trans.match(result.io.handle_result(io_result))

#     @do(NS[PluginState[S, D, CC], R])
#     def dispatch_output_aggregate(self, result: DispatchOutputAggregate) -> Do:
#         yield result.results.traverse(execute_dispatch_output.match, NS)

#     @do(NS[PluginState[S, D, CC], R])
#     def dispatch_do(self, result: DispatchDo) -> Do:
#         yield eval_trans.match(result.trans.action)

#     @do(NS[PluginState[S, D, CC], R])
#     def dispatch_log(self, result: DispatchLog) -> Do:
#         custom_logger = yield NS.inspect(_.state.logger)
#         logger = custom_logger | (lambda: dispatch_log.match)
#         yield logger(result.trans)


def arg_parser(handler: RequestHandler, params_spec: ParamsSpec) -> ArgParser:
    tpe = JsonArgParser if handler.json else TokenArgParser
    return tpe(params_spec)


def parse_args(handler: RequestHandler, args: List[Any]) -> NS[D, List[Any]]:
    return arg_parser(handler, handler.program.params_spec).parse(args)


def log_trans(trans: Program) -> NS[PluginState[S, D, CC], None]:
    return NS.pure(None) if trans.name in ('trans_log', 'pure') else NS.modify(__.log_trans(trans.name))


@do(NS)
def run_request_handler(handler: RequestHandler, args: List[Any]) -> Do:
    program = handler.program
    parsed_args = yield NS.from_either(parse_args(handler, args))
    yield log_trans(program)
    yield run_prog(program, parsed_args)


@do(NS)
def traverse_programs(dispatches: List[Program], args: List[Any]) -> Do:
    yield dispatches.traverse(lambda a: run_request_handler(a, args), NS)


# TODO use from request_handler, since there is no concurrency handling anywhere else anymore.
@do(NvimIO[A])
def exclusive(holder: PluginStateHolder, f: Callable[[], NvimIO[Tuple[PluginState, A]]], desc: str) -> Do:
    '''this is the central unsafe function, using a lock and updating the state in `holder` in-place.
    '''
    yield holder.acquire()
    ribo_log.debug2(lambda: f'exclusive: {desc}')
    state, response = yield N.ensure_failure(f(), holder.release)
    yield N.delay(lambda v: holder.update(state))
    yield holder.release()
    ribo_log.debug2(lambda: f'release: {desc}')
    yield N.pure(response)


def exclusive_dispatch(holder: PluginStateHolder, dispatch: Program, args: List[Any], desc: str) -> NvimIO[R]:
    return exclusive(
        holder,
        lambda: run_request_handler(dispatch, args).run(holder.state),
        desc
    )


def execute(state: PluginStateHolder[D], program: Program, args: List[Any]) -> NvimIO[Any]:
    return exclusive_dispatch(state, program, args, program.name)


def regular_dispatches(name: str) -> EitherState[DispatchJob, List[Program]]:
    return EitherState.inspect_f(lambda job: job.programs.lift(name).to_either(f'no dispatch for {name}'))


def special_dispatches_sync(parts: List[str]) -> EitherState[DispatchJob, List[Program]]:
    return regular_dispatches(parts.mk_string(':'))


def special_dispatches(head: str, tail: List[str]) -> EitherState[DispatchJob, List[Program]]:
    return (
        special_dispatches_sync(tail)
        if head == 'sync' else
        regular_dispatches(tail.cons(head).mk_string(':'))
    )


@do(EitherState[DispatchJob, List[Program]])
def job_dispatches() -> Do:
    name = yield EitherState.inspect(_.name)
    parts = Lists.split(name, ':')
    yield parts.detach_head.map2(special_dispatches) | (lambda: regular_dispatches(name))


@do(NvimIO[List[Any]])
def execute_dispatch_job(job: DispatchJob) -> Do:
    dispatches = yield N.e(job_dispatches().run_a(job))
    result = yield dispatches.traverse(L(execute)(job.state, _, job.args), NvimIO)
    ribo_log.debug(f'async job {job.name} completed')
    yield N.from_io(job.state.dispatch_complete())
    yield N.pure(result)


class request_result(Case, alg=NResult):

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


def execute_request(vim: NvimApi, state: PluginStateHolder[D], name: str, args: tuple, sync: bool) -> Any:
    sync_prefix = '' if sync else 'a'
    job = dispatch_job(state, name, args, sync)
    ribo_log.debug(f'dispatching {sync_prefix}sync request: {job.name}({job.args})')
    result = request_result(job)(execute_dispatch_job(job).result(vim))
    if sync:
        ribo_log.debug(f'request `{job.name}` completed: {result}')
    return decode(result)


__all__ = ('execute_dispatch_job', 'execute', 'traverse_programs', 'compute_dispatch')
