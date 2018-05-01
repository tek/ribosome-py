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
from ribosome.compute.program import Program
from ribosome import NvimApi
from ribosome.nvim.io.data import NResult, NSuccess, NError, NFatal
from ribosome.nvim.io.api import N
from ribosome.request.job import RequestJob
from ribosome.request.handler.handler import RequestHandler, RpcProgram
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
CC = TypeVar('CC')


# class execute_io(Case, alg=DIO):

#     def iodio(self, io: IODIO[A]) -> NS[PluginState[D, CC], TransComplete]:
#         return NS.from_io(io.io)

#     def gather_i_os_dio(self, io: GatherIOsDIO[A]) -> NS[PluginState[D, CC], TransComplete]:
#         def gather() -> R:
#             gio = io.io
#             return gather_ios(gio.ios, gio.timeout)
#         return NS.from_io(IO.delay(gather))

#     def gather_subprocs_dio(self, io: GatherSubprocsDIO[A, TransComplete]) -> NS[PluginState[D, CC], TransComplete]:
#         ribo_log.debug(f'gathering {io}')
#         def gather() -> TransComplete:
#             gio = io.io
#             popens = gio.procs.map(__.execute(gio.timeout))
#             return gather_ios(popens, gio.timeout)
#         return NS.from_io(IO.delay(gather))

#     def nvim_iodio(self, io: NvimIODIO[A]) -> NS[PluginState[D, CC], TransComplete]:
#         return NS.lift(io.io)


# class program_log(Case, alg=LogMessage):

#     def info(self, msg: Info) -> NS[D, None]:
#         return NS.delay(lambda v: ribo_log.info(msg.message))

#     def error(self, msg: Error) -> NS[D, None]:
#         return NS.delay(lambda v: ribo_log.error(msg))


def arg_parser(rpc_program: RpcProgram, params_spec: ParamsSpec) -> ArgParser:
    tpe = JsonArgParser if rpc_program.options.json else TokenArgParser
    return tpe(params_spec)


def parse_args(rpc_program: RpcProgram, args: List[Any]) -> NS[D, List[Any]]:
    return arg_parser(rpc_program, rpc_program.program.params_spec).parse(args)


@do(NS)
def run_request_handler(handler: RequestHandler, args: List[Any]) -> Do:
    parsed_args = yield NS.from_either(parse_args(handler, args))
    yield run_prog(handler.program, parsed_args)


@do(NS)
def traverse_programs(programs: List[Program], args: List[Any]) -> Do:
    yield programs.traverse(lambda a: run_request_handler(a, args), NS)


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


def exclusive_program(holder: PluginStateHolder, program: Program, args: List[Any]) -> NvimIO[R]:
    return exclusive(
        holder,
        lambda: run_request_handler(program, args).run(holder.state),
        program.name
    )


@do(EitherState[RequestJob, List[Program]])
def regular_programs(name: str) -> Do:
    yield EitherState.inspect_f(lambda job: job.programs.lift(name).to_either(f'no program for {name}'))


def special_programs_sync(parts: List[str]) -> EitherState[RequestJob, List[Program]]:
    return regular_programs(parts.mk_string(':'))


def special_programs(head: str, tail: List[str]) -> EitherState[RequestJob, List[Program]]:
    return (
        special_programs_sync(tail)
        if head == 'sync' else
        regular_programs(tail.cons(head).mk_string(':'))
    )


@do(EitherState[RequestJob, List[Program]])
def job_programs() -> Do:
    name = yield EitherState.inspect(_.name)
    parts = Lists.split(name, ':')
    yield parts.uncons.map2(special_programs) | (lambda: regular_programs(name))


@do(NvimIO[List[Any]])
def execute_request_job(job: RequestJob) -> Do:
    programs = yield N.e(job_programs().run_a(job))
    result = yield programs.traverse(L(exclusive_program)(job.state, _, job.args), NvimIO)
    ribo_log.debug(f'async job {job.name} completed')
    yield N.from_io(job.state.request_complete())
    yield N.pure(result)


class request_result(Case, alg=NResult):

    def __init__(self, desc: str, sync: bool) -> None:
        self.desc = desc
        self.sync = sync

    def n_success(self, result: NSuccess[List[Any]]) -> Any:
        desc = self.desc
        def multiple_results() -> int:
            ribo_log.error(f'multiple request handlers for {desc}')
            return 4
        def sync_result(head: Any, tail: List[Any]) -> Any:
            return head if tail.empty else multiple_results()
        def empty_result() -> int:
            ribo_log.error(f'no result in {desc}')
            return 3
        return result.value.uncons.map2(sync_result) | empty_result if self.sync else 0

    def n_error(self, result: NError[List[Any]]) -> Any:
        ribo_log.error(result.error)
        return 1

    def n_fatal(self, result: NFatal[List[Any]]) -> Any:
        exc = result.exception
        tb = format_exception(exc).join_lines
        desc = self.desc
        ribo_log.error(f'fatal error in {desc}')
        ribo_log.debug(f'{desc} failed:\n{tb}')
        return 2


def request_job(state: PluginStateHolder[D], name: str, args: List[Any], sync: bool) -> RequestJob:
    decoded_args = decode(args)
    fun_args = decoded_args.head | Nil
    bang = decoded_args.lift(1).contains(1)
    return RequestJob(state, decode(name), fun_args, sync, bang)


@do(NvimIO[Any])
def execute_request_io(state: PluginStateHolder[D], name: str, args: List[Any], sync: bool) -> Do:
    job = request_job(state, name, args, sync)
    ribo_log.debug(f'dispatching {job.desc}')
    result = yield execute_request_job(job)
    if sync:
        ribo_log.debug(f'request `{job.name}` completed: {result}')
    return decode(result)


def execute_request(vim: NvimApi, state: PluginStateHolder[D], name: str, args: List[Any], sync: bool) -> Any:
    job = request_job(state, name, args, sync)
    ribo_log.debug(f'dispatching {job.desc}')
    result = request_result(job.desc, job.sync)(execute_request_job(job).result(vim))
    if sync:
        ribo_log.debug(f'request `{job.name}` completed: {result}')
    return decode(result)


__all__ = ('execute_request_job', 'traverse_programs')
