from typing import Callable, TypeVar, Tuple, Any, Type

from amino import Either, do, Do, _, IO, List
from amino.logging import module_log

from ribosome.compute.tpe import prog_type
from ribosome.compute.wrap import prog_wrappers
from ribosome.compute.output import (ProgOutput, ProgOutputUnit, ProgOutputResult, ProgOutputIO, ProgScalarIO,
                                     ProgGatherIOs, ProgScalarSubprocess, ProgGatherSubprocesses, Echo, ProgIOEcho,
                                     GatherSubprocesses, GatherIOs, Gather, ProgGather)
from ribosome.nvim.io.state import NS
from ribosome.compute.wrap_data import ProgWrappers
from ribosome.config.basic_config import NoData
from ribosome.compute.ribosome import Ribosome
from ribosome.compute.tpe_data import ribo_state_prog
from ribosome.compute.prog import Prog
from ribosome.compute.program import Program, ProgramBlock, ProgramCompose
from ribosome.process import Subprocess
from ribosome.rpc.args import ParamsSpec
from ribosome.rpc.api import RpcProgram
from ribosome.rpc.arg_parser import ArgParser, JsonArgParser, TokenArgParser

log = module_log()
A = TypeVar('A')
B = TypeVar('B')
D = TypeVar('D')
P = TypeVar('P')
R = TypeVar('R')
CC = TypeVar('CC')
C = TypeVar('C')


def arg_parser(rpc_program: RpcProgram, params_spec: ParamsSpec) -> ArgParser:
    tpe = JsonArgParser if rpc_program.options.json else TokenArgParser
    return tpe(params_spec)


def parse_args(rpc_program: RpcProgram, args: List[Any]) -> NS[D, List[Any]]:
    return arg_parser(rpc_program, rpc_program.program.params_spec).parse(args)


def prog_type_error(func: Callable[[P], NS[R, A]], error: str) -> None:
    raise Exception(f'program `{func.__name__}` has invalid type: {error}')


def program_from_data(
        func: Callable[[P], NS[R, A]],
        params_spec: ParamsSpec,
        wrappers: ProgWrappers,
        interpreter: ProgOutput[A, B],
        original_module: str=None,
        original_name: str=None,
) -> Program[A]:
    name = original_name or func.__name__
    return Program.cons(
        name,
        ProgramBlock(name, func, wrappers, interpreter),
        params_spec,
        original_module,
        original_name,
    )


def prog_state(
        func: Callable[[P], NS[R, A]],
        interpreter: ProgOutput[A, B],
        original_module: str=None,
        original_name: str=None,
) -> Program:
    params_spec = ParamsSpec.from_function(func)
    wrappers = prog_type(func, params_spec).value_or(lambda err: prog_type_error(func, err))
    return Program.cons(
        func.__name__,
        ProgramBlock(func.__name__, func, wrappers, interpreter),
        params_spec,
        original_module,
        original_name,
    )


def func_state_data(f: Callable[..., NS[R, A]]) -> Tuple[ParamsSpec, ProgWrappers]:
    params_spec = ParamsSpec.from_function(f)
    @do(Either[str, ProgWrappers])
    def wrappers() -> Do:
        comp_type = yield params_spec.state_type.to_either('no state type')
        state_prog = ribo_state_prog(comp_type)
        yield prog_wrappers.match(state_prog)
    wrappers = wrappers().value_or(lambda err: prog_type_error(f, err))
    return params_spec, wrappers


class prog_io:

    def __new__(cls, func: Callable[[P], NS[D, IO[A]]]) -> Program[A]:
        return prog_state(func, ProgOutputIO(ProgScalarIO()))

    @staticmethod
    def gather(func: Callable[[P], NS[D, GatherIOs[A]]]) -> Program[List[Either[str, A]]]:
        return prog_state(func, ProgOutputIO(ProgGatherIOs()))


class prog_subproc:

    def __new__(cls, func: Callable[[P], NS[D, Subprocess[A]]]) -> Program[A]:
        return prog_state(func, ProgOutputIO(ProgScalarSubprocess()))

    @staticmethod
    def gather(func: Callable[[P], NS[D, GatherSubprocesses[A]]]) -> Program[List[Either[str, A]]]:
        return prog_state(func, ProgOutputIO(ProgGatherSubprocesses()))


class ProgApi:

    def __call__(self, func: Callable[[P], NS[D, A]]) -> Program[A]:
        return prog_state(func, ProgOutputResult())

    def unit(self, func: Callable[[P], NS[D, None]]) -> Program[None]:
        return prog_state(func, ProgOutputUnit())

    def result(self, func: Callable[[P], NS[D, A]]) -> Program[A]:
        return prog_state(func, ProgOutputResult())

    def strict(self, func: Callable[[P], A]) -> Program[A]:
        def wrap(*p: P) -> NS[NoData, A]:
            return NS.pure(func(*p))
        return prog_state(wrap, ProgOutputResult(), func.__module__, func.__name__)

    def do(self, rettype: Type[A]=None) -> Program[A]:
        def do_wrap(func: Callable[[P], Do]) -> Program[A]:
            f = do(Prog[A])(func)
            params_spec = ParamsSpec.from_function(f)
            return Program.cons(func.__name__, ProgramCompose(f), params_spec)
        return do_wrap

    io = prog_io
    subproc = prog_subproc

    def comp(self, f: Callable[[P], NS[C, A]]) -> Program[A]:
        params_spec, wrappers = func_state_data(f)
        @do(NS[Ribosome[D, CC, C], A])
        def zoomed(*p: P) -> Do:
            comp_lens = yield NS.inspect(_.comp_lens)
            yield f(*p).zoom(comp_lens)
        return program_from_data(zoomed, params_spec, wrappers, ProgOutputResult(), f.__module__, f.__name__)

    def echo(self, f: Callable[[P], NS[D, Echo]]) -> Program[None]:
        return prog_state(f, ProgOutputIO(ProgIOEcho()))

    def gather(self, func: Callable[[P], NS[D, Gather[A]]]) -> Program[List[Either[str, A]]]:
        return prog_state(func, ProgOutputIO(ProgGather()))


prog = ProgApi()


__all__ = ('prog',)
