from typing import TypeVar, Generic, Callable

from amino import ADT, Maybe, Either
from amino.tc.monad import Monad
from amino.dat import ADTMeta
from amino.func import CallByName, call_by_name
from amino.tc.base import ImplicitsMeta, Implicits

from ribosome.compute.wrap_data import ProgWrappers
from ribosome.nvim.io.state import NS
from ribosome.compute.output import ProgOutput

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
    def m(fa: Maybe[A], error: CallByName) -> 'Prog[A]':
        return Prog.from_maybe(fa, error)

    @staticmethod
    def from_either(fa: Either[str, A]) -> 'Prog[A]':
        return fa.cata(Prog.error, Prog.pure)

    @staticmethod
    def e(fa: Either[str, A]) -> 'Prog[A]':
        return Prog.from_either(fa)

    @staticmethod
    def pure(a: A) -> 'Prog[A]':
        return ProgPure(a)

    @staticmethod
    def error(error: CallByName) -> 'Prog[A]':
        return ProgError(call_by_name(error))


class ProgExec(Generic[A, B, S, R], Prog[B]):

    def __init__(
            self,
            name: str,
            code: NS[R, A],
            wrappers: ProgWrappers[S, R],
            output_type: ProgOutput,
    ) -> None:
        self.name = name
        self.code = code
        self.wrappers = wrappers
        self.output_type = output_type


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


class Monad_Prog(Monad, tpe=Prog):

    def pure(self, a: A) -> Prog[A]:
        return Prog.pure(a)

    def flat_map(self, fa: Prog[A], f: Callable[[A], Prog[B]]) -> Prog[B]:
        return ProgBind(fa, f)


__all__ = ('Prog', 'ProgBind', 'ProgPure', 'ProgPure', 'ProgError')
