from typing import Any, Callable, TypeVar

from amino import List, do, Do, Nil
from amino.logging import module_log
from amino.util.string import decode

from ribosome.nvim.io.compute import NvimIO
from ribosome.rpc.comm import StateGuard, exclusive_ns
from ribosome.nvim.io.api import N
from ribosome.compute.program import Program
from ribosome.nvim.io.state import NS
from ribosome.data.plugin_state import PS
from ribosome.compute.run import run_prog
from ribosome.compute.api import parse_args
from ribosome.rpc.api import RpcProgram
from ribosome.rpc.data.rpc import RpcArgs
from ribosome.nvim.api.util import nvimio_repeat_timeout

log = module_log()
A = TypeVar('A')


@do(NS[PS, Any])
def run_program(rpc_program: RpcProgram, args: RpcArgs) -> Do:
    parsed_args = yield NS.from_either(parse_args(rpc_program, args.args))
    yield run_prog(rpc_program.program, parsed_args)


def run_programs(programs: List[Program], args: RpcArgs) -> NvimIO[List[Any]]:
    return programs.traverse(lambda a: run_program(a, args), NvimIO)


def run_program_exclusive(guard: StateGuard[A], program: RpcProgram, args: RpcArgs) -> NvimIO[Any]:
    return (
        exclusive_ns(guard, program.program.name, run_program, program, args)
        if program.options.write else
        run_program(program, args).run_a(guard.state)
    )


def run_programs_exclusive(guard: StateGuard[A], programs: List[Program], args: RpcArgs) -> NvimIO[List[Any]]:
    return programs.traverse(lambda a: run_program_exclusive(guard, a, args), NvimIO)


def no_programs_for_rpc(method: str, args: RpcArgs) -> NvimIO[A]:
    return N.error(f'no programs defined for request {method}({args.string})')


def decode_args(args: List[Any]) -> RpcArgs:
    decoded_args = decode(args)
    fun_args = decoded_args.head | Nil
    bang = decoded_args.lift(1).contains(1)
    return RpcArgs(fun_args, bang)


def rpc_handler(guard: StateGuard[A]) -> Callable[[str, List[Any]], NvimIO[List[Any]]]:
    @do(NvimIO[List[Any]])
    def handler(method: str, raw_args: List[Any]) -> Do:
        yield nvimio_repeat_timeout(lambda: N.pure(guard), lambda a: a.initialized, '''state wasn't initialized''', 20)
        args = decode_args(raw_args)
        log.debug(f'handling request: {method}({args.args.join_comma})')
        programs = guard.state.programs_by_name(method)
        yield (
            no_programs_for_rpc(method, args)
            if programs.empty else
            run_programs_exclusive(guard, programs, args)
        )
    return handler


__all__ = ('rpc_handler', 'run_program', 'run_programs', 'run_program_exclusive', 'run_programs_exclusive',
           'no_programs_for_rpc', 'decode_args', 'rpc_handler',)
