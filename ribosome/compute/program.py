from typing import TypeVar, Generic, Callable, Any, Type

from amino import ADT, Dat, List, Lists, Nil, Either
from amino.case import Case
from amino.json.encoder import Encoder
from amino.json.data import JsonError, Json
from amino.json.encoders import encode_instance
from amino.json.decoder import Decoder
from amino.json.decoders import decode_instance

from ribosome.compute.wrap_data import ProgWrappers
from ribosome.compute.output import ProgOutput, ProgOutputResult
from ribosome.nvim.io.state import NS
from ribosome.compute.prog import Prog, ProgBind, ProgExec
from ribosome.rpc.args import ParamsSpec

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
            name: str,
            code: Callable[..., NS[D, A]],
            wrappers: ProgWrappers,
            interpreter: ProgOutput[A, B],
    ) -> None:
        self.name = name
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
            ProgramBlock(f.__name__, f, ProgWrappers.id(), ProgOutputResult()),
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
        return ProgExec(code.name, code.code(*self.args), code.wrappers, code.interpreter)


def bind_program(program: Program[A], args: List[Any]) -> Prog[B]:
    return bind_program_code(program, args)(program.code)


def bind_nullary_program(program: Program[A]) -> Prog[B]:
    return bind_program(program, Nil)


def bind_programs(programs: List[Program[A]], args: List[Any]) -> Prog[B]:
    return programs.traverse(lambda a: bind_program(a, args), Prog)


class ProgramEncoder(Encoder[Program], tpe=Program):

    def encode(self, prog: Program) -> Either[JsonError, Json]:
        return encode_instance(prog, Program, prog.code.code.__module__, prog.code.code.__name__)


class ProgramDecoder(Decoder[Program], tpe=Program):

    def decode(self, tpe: Type[Program], data: Json) -> Either[JsonError, Program]:
        return decode_instance(data, 'Program')


__all__ = ('Program', 'bind_program', 'bind_nullary_program', 'bind_programs')
