from typing import TypeVar, Generic, Callable, Any

from amino import ADT, Dat, Maybe, Either, List, Lists, Nil
from amino.tc.monad import Monad
from amino.dat import ADTMeta
from amino.func import CallByName, call_by_name
from amino.case import Case
from amino.tc.base import ImplicitsMeta, Implicits

from ribosome.compute.wrap_data import ProgWrappers
from ribosome.compute.output import ProgOutputInterpreter
from ribosome.nvim.io.state import NS
from ribosome.request.args import ParamsSpec

A = TypeVar('A')
B = TypeVar('B')
D = TypeVar('D')
M = TypeVar('M')
P = TypeVar('P')
S = TypeVar('S')
R = TypeVar('R')


class ProgMeta(ADTMeta, ImplicitsMeta):

    @property
    def unit(self) -> 'Prog[None]':
        return Prog.pure(None)


class Prog(Generic[A], ADT['Prog[A]'], Implicits, implicits=True, auto=True, metaclass=ProgMeta):

    @staticmethod
    def from_maybe(fa: Maybe[A], error: CallByName) -> 'Prog[A]':
        return fa / Prog.pure | (lambda: Prog.error(error))

    @staticmethod
    def from_either(fa: Either[str, A]) -> 'Prog[A]':
        return fa.cata(Prog.error, Prog.pure)

    @staticmethod
    def pure(a: A) -> 'Prog[A]':
        return ProgPure(a)

    @staticmethod
    def error(error: CallByName) -> 'Prog[A]':
        return ProgError(call_by_name(error))


class ProgExec(Generic[A, B, S, R], Prog[B]):

    def __init__(
            self,
            code: NS[R, A],
            wrappers: ProgWrappers[S, R],
            interpreter: ProgOutputInterpreter[A, B],
    ) -> None:
        self.code = code
        self.wrappers = wrappers
        self.interpreter = interpreter


class ProgBind(Generic[A, B], Prog[B]):

    def __init__(self, fa: Prog[A], f: Callable[[A], Prog[B]]) -> None:
        self.fa = fa
        self.f = f


class ProgPure(Generic[A], Prog[A]):

    def __init__(self, value: A) -> None:
        self.value = value


class ProgError(Generic[A], Prog[A]):

    def __init__(self, msg: str) -> None:
        self.msg = msg


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

    def __call__(self, *args: Any) -> Prog:
        return bind_program(self, Lists.wrap(args))


class bind_program_code(Case[ProgramCode[A], Prog[A]], alg=ProgramCode):

    def __init__(self, program: Program[A], args: List[Any]) -> None:
        self.args = args

    def program_compose(self, code: ProgramCompose[A]) -> Prog[A]:
        return code.code(*self.args)

    def program_block(self, code: ProgramBlock[Any, A, Any]) -> Prog[A]:
        return ProgExec(code.code(*self.args), code.wrappers, code.interpreter)


def bind_program(program: Program[A], args: List[Any]) -> Prog[A]:
    return bind_program_code(program, args)(program.code)


def bind_nullary_program(program: Program[A]) -> Prog[A]:
    return bind_program(program, Nil)


def bind_programs(programs: List[Program[A]], args: List[Any]) -> Prog[A]:
    return programs.traverse(lambda a: bind_program(a, args), Prog)


class Monad_Prog(Monad, tpe=Prog):

    def pure(self, a: A) -> Prog[A]:
        return Prog.pure(a)

    def flat_map(self, fa: Prog[A], f: Callable[[A], Prog[B]]) -> Prog[B]:
        return ProgBind(fa, f)


__all__ = ('Prog', 'ProgBind', 'ProgPure', 'ProgPure', 'ProgError', 'Program', 'bind_program', 'bind_nullary_program',
           'bind_programs')
