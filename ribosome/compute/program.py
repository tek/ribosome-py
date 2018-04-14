from typing import TypeVar, Generic, Callable, Any

from amino import ADT, Dat, List, Lists, Nil, do, Do
from amino.case import Case

from ribosome.compute.wrap_data import ProgWrappers
from ribosome.compute.output import ProgOutputInterpreter
from ribosome.nvim.io.state import NS
from ribosome.request.args import ParamsSpec
from ribosome.compute.prog import Prog, ProgBind, ProgExec, ProgInterpret

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
            interpreter: ProgOutputInterpreter[A, B],
    ) -> None:
        self.code = code
        self.wrappers = wrappers
        self.interpreter = interpreter


class ProgramCompose(Generic[A], ProgramCode[A]):

    def __init__(self, code: Callable[..., ProgBind[Any, A]]) -> None:
        self.code = code


class Program(Generic[A], Dat['Program[A]']):

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
        return bind_program(self, passthrough_interpreter, Lists.wrap(args))


class ProgramInterpreter(Generic[A, B, R]):

    def __init__(self, interpret: Callable[[A], Callable[[R], Prog[B]]]) -> None:
        self.interpret = interpret


passthrough_interpreter = ProgramInterpreter(lambda r: Prog.pure)


class bind_program_code(Generic[A, B, R], Case[ProgramCode[A], Prog[B]], alg=ProgramCode):

    def __init__(self, program: Program[A], interpreter: ProgramInterpreter[A, B, R], args: List[Any]) -> None:
        self.interpreter = interpreter
        self.args = args

    def program_compose(self, code: ProgramCompose[A]) -> Prog[A]:
        return code.code(*self.args)

    @do(Prog[A])
    def program_block(self, code: ProgramBlock[Any, A, R]) -> Do:
        exe = ProgExec(code.code(*self.args), code.wrappers)
        yield ProgInterpret(exe, self.interpreter.interpret(code.interpreter))


def bind_program(program: Program[A], interpreter: ProgramInterpreter[A, B, C], args: List[Any]) -> Prog[B]:
    return bind_program_code(program, interpreter, args)(program.code)


def bind_nullary_program(program: Program[A], interpreter: ProgramInterpreter[A, B, C]) -> Prog[B]:
    return bind_program(program, interpreter, Nil)


def bind_programs(programs: List[Program[A]], interpreter: ProgramInterpreter[A, B, C], args: List[Any]) -> Prog[B]:
    return programs.traverse(lambda a: bind_program(a, args), interpreter, Prog)


__all__ = ('Program', 'bind_program', 'bind_nullary_program', 'bind_programs')
