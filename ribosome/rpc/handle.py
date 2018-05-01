from concurrent.futures import Future
from typing import Any, Callable, TypeVar

import msgpack

from amino import List, do, Do, Try, _, IO, Nil
from amino.state import EitherState
from amino.lenses.lens import lens
from amino.logging import module_log
from amino.util.string import decode

from ribosome.rpc.error import RpcReadError
from ribosome.nvim.io.compute import NvimIO
from ribosome.request.execute import execute_request_io, request_job, job_programs, parse_args
from ribosome.rpc.comm import Comm, RpcComm, RpcConcurrency, Rpc, StateGuard, exclusive_ns
from ribosome.nvim.io.api import N
from ribosome.compute.program import Program
from ribosome import ribo_log
from ribosome.nvim.io.state import NS
from ribosome.data.plugin_state import PS
from ribosome.request.handler.handler import RpcProgram, RpcArgs
from ribosome.compute.run import run_prog

log = module_log()
A = TypeVar('A')


# FIXME loop is not part of comm, but uv
# add `stop` handler to `RpcComm`?
def rpc_error(comm: Comm) -> Callable[[RpcReadError], None]:
    def on_error(error: RpcReadError) -> IO[None]:
        return IO.pure(None)
        # IO.delay(comm.loop.stop)
    return on_error


def exclusive_increment(concurrency: RpcConcurrency) -> None:
    with concurrency.lock:
        concurrency.requests.current_id += 1


def exclusive_register_callback(concurrency: RpcConcurrency, id: int, rpc: Rpc) -> Future:
    result = Future()
    with concurrency.lock:
        concurrency.requests.to_vim.update({id: (result, rpc)})
    return result


@do(EitherState[RpcConcurrency, int])
def increment() -> Do:
    yield EitherState.inspect(exclusive_increment)
    yield EitherState.inspect(_.requests.current_id)


@do(EitherState[RpcComm, Any])
def send_rpc(metadata: list, rpc: Rpc) -> Do:
    send = yield EitherState.inspect(lambda a: a.send)
    payload = yield EitherState.lift(Try(msgpack.packb, metadata + [rpc.method.encode(), rpc.args]))
    yield EitherState.lift(Try(send, payload))


@do(EitherState[Comm, Any])
def send_request(rpc: Rpc, timeout: float) -> Do:
    id = yield increment().zoom(lens.concurrency)
    result = yield EitherState.inspect(lambda a: exclusive_register_callback(a.concurrency, id, rpc))
    yield send_rpc([0, id], rpc).zoom(lens.rpc)
    yield EitherState.lift(Try(result.result, timeout).lmap(lambda a: f'{rpc} timed out after {timeout}s'))


@do(EitherState[Comm, Any])
def send_notification(rpc: Rpc, timeout: float) -> Do:
    yield send_rpc([2], rpc).zoom(lens.rpc)


@do(NS[PS, Any])
def run_program(rpc_program: RpcProgram, args: RpcArgs) -> Do:
    parsed_args = yield NS.from_either(parse_args(rpc_program, args.args))
    yield run_prog(rpc_program.program, parsed_args)


def run_program_exclusive(guard: StateGuard[A], program: RpcProgram, args: RpcArgs) -> NvimIO[Any]:
    return exclusive_ns(guard, program.program.name, run_program, program, args)


def run_programs_exclusive(guard: StateGuard[A], programs: List[Program], args: RpcArgs) -> NvimIO[Any]:
    return programs.traverse(lambda a: run_program_exclusive(guard, a, args), NvimIO)


def no_programs_for_rpc(method: str, args: RpcArgs) -> NvimIO[None]:
    return N.error(f'no programs defined for request {method}({args.string})')


def decode_args(args: List[Any]) -> RpcArgs:
    decoded_args = decode(args)
    fun_args = decoded_args.head | Nil
    bang = decoded_args.lift(1).contains(1)
    return RpcArgs(fun_args, bang)


# FIXME `request_result` is not called with `run_program`
def comm_request_handler(guard: StateGuard[A]) -> Callable[[str, List[Any], bool], NvimIO[Any]]:
    @do(NvimIO[Any])
    def handler(method: str, raw_args: List[Any], sync: bool) -> Do:
        args = decode_args(raw_args)
        log.debug(f'handling request: {method}({args.args.join_tokens})')
        programs = guard.state.programs.filter(lambda a: a.program.name == method)
        yield (
            no_programs_for_rpc(method, args)
            if programs.empty else
            run_programs_exclusive(guard, programs, args)
        )
    return handler


__all__ = ()
