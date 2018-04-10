from typing import Type, TypeVar, Generic, Callable

from amino import List, Dat, IO, __
from amino.tc.base import Implicits
from amino.tc.functor import Functor
from amino.dat import DatImplicitsMeta

from ribosome.compute.prog import Program
from ribosome.process import Subprocess


A = TypeVar('A')
B = TypeVar('B')


class GatherIOs(Generic[A], Dat['GatherIOs[A]'], Implicits, implicits=True, auto=True, metaclass=DatImplicitsMeta):

    def __init__(self, ios: List[IO[A]], handle_result: Program, timeout: float=None) -> None:
        self.ios = ios
        self.handle_result = handle_result
        self.timeout = timeout


class GatherIOsFunctor(Functor, tpe=GatherIOs):

    def map(self, fa: GatherIOs[A], f: Callable[[A], B]) -> None:
        return GatherIOs(fa.ios.map(__.map(f)), fa.handle_result, fa.timeout)


class GatherSubprocs(
        Generic[A, B],
        Dat['GatherSubprocs[A, B]'],
        Implicits,
        implicits=True,
        auto=True,
        metaclass=DatImplicitsMeta
):

    def __init__(self, procs: List[Subprocess[A]], handle_result: Program, timeout: float=None) -> None:
        self.procs = procs
        self.handle_result = handle_result
        self.timeout = timeout


__all__ = ('GatherIOs', 'GatherSubprocs')
