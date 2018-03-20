from typing import TypeVar, Type, Generic, Any

from amino import Either, List, IO, L, _
from amino.state import StateT

from ribosome.nvim import NvimIO
from ribosome.trans.action import TransUnit, TransResult, TransIO, LogMessage, TransLog
from ribosome.trans.effect import TransEffect
from ribosome.trans.run import cont, lift
from ribosome.trans.step import TransStep, TransEffectError, Lift, Strict

D = TypeVar('D')
A = TypeVar('A')
B = TypeVar('B')
R = TypeVar('R')
N = TypeVar('N')
G = TypeVar('G')
O = TypeVar('O')


class TransEffectStateT(Generic[G, D, R], TransEffect[StateT[G, D, R]]):

    def check(self, result: TransEffect[R]) -> None:
        return (
            TransEffectError(f'`State` trans result `{result}` is not a `TransStep`')
            if not isinstance(result, TransStep) else
            TransEffectError('found nested `State` in transition result')
            if result.strict else
            TransEffectError(result.data)
            if result.error else
            result.data
        )

    @property
    def tpe(self) -> Type[StateT[G, D, R]]:
        return StateT

    def extract(self, data: StateT[G, D, R], tail: List[TransEffect], in_state: bool) -> TransStep:
        return (
            TransEffectError('cannot nest `StateT` in transition result')
            if in_state else
            Strict(cont(tail, True, lambda run: data.map(lambda inner: self.check(run(inner)))) | data)
        )


class TransEffectIO(Generic[R], TransEffect[IO[R]]):

    @property
    def tpe(self) -> Type[IO[R]]:
        return IO

    def extract(self, data: IO[R], tail: List[TransEffect], in_state: bool) -> TransStep:
        io = cont(tail, False, data.map) | data
        return Lift(TransIO(io.map(L(lift.match)(_, in_state))))


class TransEffectNvimIO(Generic[R], TransEffect[NvimIO[R]]):

    @property
    def tpe(self) -> Type[NvimIO[R]]:
        return NvimIO

    def extract(self, data: NvimIO[R], tail: List[TransEffect], in_state: bool) -> TransStep:
        io = cont(tail, False, data.map) | data
        return Lift(TransIO(io.map(L(lift.match)(_, in_state))))


class TransEffectUnit(TransEffect[None]):

    @property
    def tpe(self) -> Type[None]:
        return type(None)

    def extract(self, data: None, tail: List[TransEffect], in_state: bool) -> Either[R, N]:
        return Lift(TransUnit()) if tail.empty else TransEffectError('cannot apply trans effects to unit')


class TransEffectResult(TransEffect[Any]):

    @property
    def tpe(self) -> Type[Any]:
        return object

    def extract(self, data: object, tail: List[TransEffect], in_state: bool) -> Either[R, N]:
        return Lift(TransResult(data)) if tail.empty else TransEffectError('cannot apply trans effects to result')


class TransEffectLog(TransEffect[LogMessage]):

    @property
    def tpe(self) -> Type[LogMessage]:
        return LogMessage

    def extract(self, data: LogMessage, tail: List[TransEffect], in_state: bool) -> TransStep:
        return Lift(TransLog(data)) if tail.empty else TransEffectError('cannot apply trans effects to LogMessage')


__all__ = ()
