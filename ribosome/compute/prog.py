from typing import TypeVar, Generic, Callable, Any

from amino import ADT, Dat, Maybe, Either, List, Lists
from amino.tc.monad import Monad
from amino.dat import ADTMeta
from amino.func import CallByName, call_by_name
from amino.case import Case

from ribosome.compute.tpe_data import ProgType
from ribosome.compute.wrap_data import ProgWrappers
from ribosome.compute.output import ProgOutputInterpreter
from ribosome.nvim.io.state import NS
from ribosome.request.args import ParamsSpec

A = TypeVar('A')
B = TypeVar('B')
D = TypeVar('D')
M = TypeVar('M')
P = TypeVar('P')


class ProgMeta(ADTMeta):

    @property
    def unit(self) -> 'Prog[None]':
        return Prog.pure(None)

    @property
    def id(self) -> 'Prog[A]':
        def f(a: A) -> A:
            return a
        return ProgMap(f)


class Prog(Generic[A], ADT['Prog[A]'], metaclass=ProgMeta):

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


class ProgExec(Generic[A, B], Prog[B]):

    def __init__(
            self,
            code: NS[D, A],
            prog_type: ProgType,
            wrappers: ProgWrappers,
            interpreter: ProgOutputInterpreter[A, B],
    ) -> None:
        self.code = code
        self.prog_type = prog_type
        self.wrappers = wrappers
        self.interpreter = interpreter


class ProgBind(Generic[A, B], Prog[B]):

    def __init__(self, fa: Prog[A], f: Callable[[A], Prog[B]]) -> None:
        self.fa = fa
        self.f = f


class ProgPure(Generic[A], Prog[A]):

    def __init__(self, value: A) -> None:
        self.value = value


class ProgMap(Generic[A, B], Prog[B]):

    def __init__(self, f: Callable[[A], B]) -> None:
        self.f = f


class ProgError(Generic[A], Prog[A]):

    def __init__(self, msg: str) -> None:
        self.msg = msg


class ProgramCode(ADT['Program']):
    pass


# TODO restrict the function to a single value parameter of type ProgramArgs[A, B], where A is a custom data type
# containing the positional args and B an optional json decoded parameter.
class ProgramBlock(ProgramCode):

    def __init__(
            self,
            code: Callable[..., NS[D, A]],
            prog_type: ProgType,
            wrappers: ProgWrappers,
            interpreter: ProgOutputInterpreter[A, B],
    ) -> None:
        self.code = code
        self.prog_type = prog_type
        self.wrappers = wrappers
        self.interpreter = interpreter


class ProgramCompose(ProgramCode):

    def __init__(self, code: Callable[..., ProgBind]) -> None:
        self.code = code


class Program(Generic[A, B], Dat['Program']):

    def __init__(
            self,
            name: str,
            code: ProgramCode,
            params_spec: ParamsSpec,
    ) -> None:
        self.name = name
        self.code = code
        self.params_spec = params_spec

    def __call__(self, *args: Any) -> Prog:
        return bind_program(self, Lists.wrap(args))


class bind_program_code(Case[ProgramCode, Prog], alg=ProgramCode):

    def __init__(self, program: Program, args: List[Any]) -> None:
        self.args = args

    def program_compose(self, code: ProgramCompose) -> Prog:
        return code.code(*self.args)

    def program_block(self, code: ProgramBlock) -> Prog:
        return ProgExec(code.code(*self.args), code.prog_type, code.wrappers, code.interpreter)


def bind_program(program: Program, args: List[Any]) -> Prog:
    return bind_program_code(program, args)(program.code)


class Monad_Prog(Monad, tpe=Prog):

    def pure(self, a: A) -> Prog[A]:
        return Prog.pure(a)

    def flat_map(self, fa: Prog[A], f: Callable[[A], Prog[B]]) -> Prog[B]:
        return ProgBind(fa, f)


__all__ = ('Prog', 'ProgBind', 'ProgPure', 'ProgPure', 'ProgError', 'Program')
