from typing import TypeVar, Generic, Callable, Any

from amino import ADT, Dat, List, Lists, Nil
from amino.case import Case

from ribosome.compute.wrap_data import ProgWrappers
from ribosome.compute.output import ProgOutput, ProgOutputResult
from ribosome.nvim.io.state import NS
from ribosome.request.args import ParamsSpec
from ribosome.compute.prog import Prog, ProgBind, ProgExec

A = TypeVar('A')
B = TypeVar('B')
C = TypeVar('C')
D = TypeVar('D')
R = TypeVar('R')


class ProgramCode(Generic[A], ADT['ProgramCode[A]']):
    pass


# TODO restrict the function to a single value parameter of type ProgramArgs[A, B], where A is a custom data type
# containing the positional args and B an optional json decoded parameter.
class ProgramBlock(Generic[A, B, D], ProgramCode[B]):

    def __init__(
            self,
            code: Callable[..., NS[D, A]],
            wrappers: ProgWrappers,
            interpreter: ProgOutput[A, B],
    ) -> None:
        self.code = code
        self.wrappers = wrappers
        self.interpreter = interpreter


class ProgramCompose(Generic[A], ProgramCode[A]):

    def __init__(self, code: Callable[..., ProgBind[Any, A]]) -> None:
        self.code = code


class Program(Generic[A], Dat['Program[A]']):

    @staticmethod
    def lift(f: Callable[..., NS[D, A]]) -> 'Program[A]':
        return Program(
            f.__name__,
            ProgramBlock(f, ProgWrappers.id(), ProgOutputResult()),
            ParamsSpec.from_function(f)
        )

    def __init__(
            self,
            name: str,
            code: ProgramCode[A],
            params_spec: ParamsSpec,
    ) -> None:
        self.name = name
        self.code = code
        self.params_spec = params_spec

    def __call__(self, *args: Any) -> Prog[A]:
        return bind_program(self, Lists.wrap(args))


class bind_program_code(Generic[A, B, R], Case[ProgramCode[A], Prog[B]], alg=ProgramCode):

    def __init__(self, program: Program[A], args: List[Any]) -> None:
        self.args = args

    def program_compose(self, code: ProgramCompose[A]) -> Prog[A]:
        return code.code(*self.args)

    def program_block(self, code: ProgramBlock[Any, A, R]) -> Prog[A]:
        return ProgExec(code.code(*self.args), code.wrappers, code.interpreter)


def bind_program(program: Program[A], args: List[Any]) -> Prog[B]:
    return bind_program_code(program, args)(program.code)


def bind_nullary_program(program: Program[A]) -> Prog[B]:
    return bind_program(program, Nil)


def bind_programs(programs: List[Program[A]], args: List[Any]) -> Prog[B]:
    return programs.traverse(lambda a: bind_program(a, args), Prog)


__all__ = ('Program', 'bind_program', 'bind_nullary_program', 'bind_programs')
