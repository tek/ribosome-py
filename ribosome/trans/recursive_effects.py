from typing import Type, TypeVar, Generic, Callable

from amino import List, Dat, IO, __
from amino.tc.base import Implicits
from amino.tc.functor import Functor

from ribosome.trans.effect import TransEffect
from ribosome.trans.handler import Trans, TransF
from ribosome.trans.step import Lift, TransEffectError, TransStep
from ribosome.trans.action import TransDo, TransIO
from ribosome.process import Subprocess


A = TypeVar('A')
B = TypeVar('B')


class TransEffectDo(TransEffect[Trans]):

    @property
    def tpe(self) -> Type[Trans]:
        return Trans

    def extract(self, data: Trans[A], tail: List[TransEffect], in_state: bool) -> TransStep:
        return Lift(TransDo(data)) if tail.empty else TransEffectError('cannot apply trans effects to Trans')


class GatherIOs(Generic[A], Dat['GatherIOs'], Implicits, implicits=True, auto=True):

    def __init__(self, ios: List[IO[A]], handle_result: TransF, timeout: float=None) -> None:
        self.ios = ios
        self.handle_result = handle_result
        self.timeout = timeout


class GatherIOsFunctor(Functor, tpe=GatherIOs):

    def map(self, fa: GatherIOs[A], f: Callable[[A], B]) -> None:
        return GatherIOs(fa.ios.map(__.map(f)), fa.handle_result, fa.timeout)


class TransEffectGatherIOs(TransEffect[GatherIOs]):

    @property
    def tpe(self) -> Type[GatherIOs]:
        return GatherIOs

    def extract(self, data: GatherIOs, tail: List[TransEffect], in_state: bool) -> TransStep:
        return Lift(TransIO(data))


class GatherSubprocs(Generic[A, B], Dat['GatherSubprocs'], Implicits, implicits=True, auto=True):

    def __init__(self, procs: List[Subprocess[A]], handle_result: TransF[B], timeout: float=None) -> None:
        self.procs = procs
        self.handle_result = handle_result
        self.timeout = timeout


class TransEffectGatherSubprocs(TransEffect[GatherSubprocs]):

    @property
    def tpe(self) -> Type[GatherSubprocs]:
        return GatherSubprocs

    def extract(self, data: GatherSubprocs, tail: List[TransEffect], in_state: bool) -> TransStep:
        return Lift(TransIO(data))


__all__ = ('GatherIOs', 'GatherSubprocs')
