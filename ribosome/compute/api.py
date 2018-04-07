from typing import Callable, TypeVar, Any

from amino import List
from amino.case import Case

from ribosome.compute.prog import Program, Prog, ProgramBlock, ProgramCompose

from ribosome.compute.tpe import analyse_trans_tpe
from ribosome.compute.wrap import prog_wrappers
from ribosome.compute.output import ProgOutputInterpreter, ProgOutputUnit, ProgOutputResult, ProgOutputIO
from ribosome.nvim.io.state import NS
from ribosome.request.args import ParamsSpec

A = TypeVar('A')
B = TypeVar('B')
D = TypeVar('D')
P = TypeVar('P')
PIO = TypeVar('PIO')


def prog_state(func: Callable[[P], NS[D, A]], interpreter: ProgOutputInterpreter[A, B]) -> Program:
    params_spec = ParamsSpec.from_function(func)
    tpe = analyse_trans_tpe(params_spec).get_or_raise()
    wrappers = prog_wrappers(tpe)
    return Program(func.__name__, ProgramBlock(func, tpe, wrappers, interpreter), params_spec)


class prog:

    @staticmethod
    def unit(func: Callable[[P], NS[D, None]]) -> Program:
        return prog_state(func, ProgOutputUnit())

    @staticmethod
    def result(func: Callable[[P], NS[D, A]]) -> Program:
        return prog_state(func, ProgOutputResult())

    @staticmethod
    def do(func: Callable[[P], Prog[A]]) -> Program:
        params_spec = ParamsSpec.from_function(func)
        return Program(func.__name__, ProgramCompose(func), params_spec)

    @staticmethod
    def io(interpreter: Callable[[PIO], NS[D, A]]) -> Callable[[Callable[[P], PIO]], Program]:
        def decorate(func: Callable[[P], PIO]) -> Program:
            return prog_state(func, ProgOutputIO(interpreter))
        return decorate


__all__ = ('ProgApi', 'prog')
