from typing import Callable, TypeVar, Tuple

from amino import Either, do, Do, _, IO, List

from ribosome.compute.tpe import analyse_prog_tpe, prog_type
from ribosome.compute.wrap import prog_wrappers
from ribosome.compute.output import (ProgOutput, ProgOutputUnit, ProgOutputResult, ProgOutputIO,
                                     ProgScalarIO, ProgGatherIOs, ProgScalarSubprocess, ProgGatherSubprocesses, Echo,
                                     ProgIOEcho)
from ribosome.nvim.io.state import NS
from ribosome.request.args import ParamsSpec
from ribosome.compute.wrap_data import ProgWrappers
from ribosome.config.settings import Settings
from ribosome.config.basic_config import NoData
from ribosome.compute.ribosome import Ribosome
from ribosome.compute.tpe_data import ribo_state_prog
from ribosome.compute.prog import Prog
from ribosome.compute.program import Program, ProgramBlock, ProgramCompose
from ribosome.process import Subprocess

A = TypeVar('A')
B = TypeVar('B')
D = TypeVar('D')
M = TypeVar('M')
P = TypeVar('P')
R = TypeVar('R')
S = TypeVar('S', bound=Settings)
CC = TypeVar('CC')
C = TypeVar('C')
PIO = TypeVar('PIO')


def prog_type_error(func: Callable[[P], NS[R, A]], error: str) -> None:
    raise Exception(f'program `{func.__name__}` has invalid type: {error}')


def program_from_data(
        func: Callable[[P], NS[R, A]],
        params_spec: ParamsSpec,
        wrappers: ProgWrappers,
        interpreter: ProgOutput[A, B],
) -> Program[A]:
    return Program(func.__name__, ProgramBlock(func, wrappers, interpreter), params_spec)


def prog_state(func: Callable[[P], NS[R, A]], interpreter: ProgOutput[A, B]) -> Program:
    params_spec = ParamsSpec.from_function(func)
    wrappers = prog_type(func, params_spec).value_or(lambda err: prog_type_error(func, err))
    return Program(func.__name__, ProgramBlock(func.__name__, func, wrappers, interpreter), params_spec)


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
    def gather(func: Callable[[P], NS[D, List[IO[A]]]]) -> Program[A]:
        return prog_state(func, ProgOutputIO(ProgGatherIOs()))


class prog_subproc:

    def __new__(cls, func: Callable[[P], NS[D, Subprocess[A]]]) -> Program[A]:
        return prog_state(func, ProgOutputIO(ProgScalarSubprocess()))

    @staticmethod
    def gather(func: Callable[[P], NS[D, List[Subprocess[A]]]]) -> Program[A]:
        return prog_state(func, ProgOutputIO(ProgGatherSubprocesses()))


class prog:

    def __new__(self, func: Callable[[P], NS[D, A]]) -> Program[A]:
        return prog_state(func, ProgOutputResult())

    @staticmethod
    def unit(func: Callable[[P], NS[D, None]]) -> Program[None]:
        return prog_state(func, ProgOutputUnit())

    @staticmethod
    def result(func: Callable[[P], NS[D, A]]) -> Program[A]:
        return prog_state(func, ProgOutputResult())

    @staticmethod
    def strict(func: Callable[[P], A]) -> Program[A]:
        def wrap(*p: P) -> NS[NoData, A]:
            return NS.pure(func(*p))
        return prog_state(wrap, ProgOutputResult())

    @staticmethod
    def do(func: Callable[[P], Do]) -> Program:
        f = do(Prog[A])(func)
        params_spec = ParamsSpec.from_function(f)
        return Program(func.__name__, ProgramCompose(f), params_spec)

    io = prog_io
    subproc = prog_subproc

    @staticmethod
    def comp(f: Callable[[P], NS[C, A]]) -> Program[A]:
        params_spec, wrappers = func_state_data(f)
        @do(NS[Ribosome[S, D, CC, C], A])
        def zoomed(*p: P) -> Do:
            comp_lens = yield NS.inspect(_.comp_lens)
            yield f(*p).zoom(comp_lens)
        return program_from_data(zoomed, params_spec, wrappers, ProgOutputResult())

    @staticmethod
    def echo(f: Callable[[P], NS[D, Echo]]) -> Program[None]:
        return prog_state(f, ProgOutputIO(ProgIOEcho()))


__all__ = ('prog',)
