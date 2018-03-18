from typing import Callable, TypeVar, Type, Generic, Awaitable, Any

from amino import Either, List, IO, L, _, Maybe, __
from amino.state import StateT
from amino.dat import Dat
from amino.tc.functor import Functor
from amino.tc.base import Implicits

from ribosome.nvim import NvimIO
from ribosome.trans.action import (Propagate, TransUnit, TransResult, TransAction, TransIO, TransM, TransDo, LogMessage,
                                   TransLog)
from ribosome.trans.message_base import Sendable, Messages
from ribosome.trans.messages import Nop, CoroutineAlg
from ribosome.process import Subprocess, SubprocessResult
from ribosome.trans.effect import TransEffect
from ribosome.trans.run import cont, lift
from ribosome.trans.step import TransStep, TransEffectError, Lift, Strict
from ribosome.trans.handler import FreeTrans

D = TypeVar('D')
A = TypeVar('A')
B = TypeVar('B')
R = TypeVar('R')
N = TypeVar('N')
G = TypeVar('G')
O = TypeVar('O')


class TransEffectMaybe(Generic[R], TransEffect[Maybe[R]]):

    @property
    def tpe(self) -> Type[Maybe[R]]:
        return Maybe

    def extract(self, data: Maybe[N], tail: List[TransEffect], in_state: bool) -> TransStep:
        nested = data.map(lambda a: cont(tail, in_state, lambda run: Lift(run(a))) | a)
        return Lift(nested | Propagate.one(Nop()))


class TransEffectEither(Generic[R], TransEffect[Either[str, R]]):

    @property
    def tpe(self) -> Type[Either[str, R]]:
        return Either

    def extract(self, data: Either[str, R], tail: List[TransEffect], in_state: bool) -> TransStep:
        nested = data.map(lambda a: cont(tail, in_state, lambda run: Lift(run(a))) | a)
        return nested.cata(TransEffectError, Lift)


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


class GatherIOs(Generic[A], Dat['GatherIOs'], Implicits, implicits=True, auto=True):

    def __init__(self, ios: List[IO[A]], handle_result: FreeTrans, timeout: float=None) -> None:
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


class GatherSubprocs(Generic[A, R], Dat['GatherSubprocs'], Implicits, implicits=True, auto=True):

    def __init__(self, procs: List[Subprocess[A]], handle_result: FreeTrans, timeout: float=None) -> None:
        self.procs = procs
        self.handle_result = handle_result
        self.timeout = timeout


class TransEffectGatherSubprocs(TransEffect[GatherSubprocs]):

    @property
    def tpe(self) -> Type[GatherSubprocs]:
        return GatherSubprocs

    def extract(self, data: GatherSubprocs, tail: List[TransEffect], in_state: bool) -> TransStep:
        return Lift(TransIO(data))


class TransEffectNvimIO(Generic[R], TransEffect[NvimIO[R]]):

    @property
    def tpe(self) -> Type[NvimIO[R]]:
        return NvimIO

    def extract(self, data: NvimIO[R], tail: List[TransEffect], in_state: bool) -> TransStep:
        io = cont(tail, False, data.map) | data
        return Lift(TransIO(io.map(L(lift.match)(_, in_state))))


class TransEffectCoro(TransEffect):

    @property
    def tpe(self) -> Type[Awaitable]:
        return Awaitable

    def extract(self, data: Awaitable, tail: List[TransEffect], in_state: bool) -> Either[R, N]:
        async def coro_map(run: Callable[[R], TransStep]) -> TransStep:
            res = await data
            return lift.match(run(res), in_state)
        coro = cont(tail, False, coro_map) | data
        return Lift(Propagate.one(CoroutineAlg(coro).pub))


class TransEffectSingleMessage(TransEffect[Sendable]):

    @property
    def tpe(self) -> Type[Sendable]:
        return Messages

    def extract(self, data: Sendable, tail: List[TransEffect], in_state: bool) -> Either[R, N]:
        return Lift(Propagate.one(data)) if tail.empty else TransEffectError('cannot apply trans effects to Sendable')


class TransEffectMessages(TransEffect[List[Sendable]]):

    @property
    def tpe(self) -> Type[List[Sendable]]:
        return List

    def typecheck(self, data: List[Sendable]) -> bool:
        return super().typecheck(data) and data.forall(lambda a: isinstance(a, Messages))

    def extract(self, data: List[Sendable], tail: List[TransEffect], in_state: bool) -> Either[R, N]:
        return Lift(Propagate(data)) if tail.empty else TransEffectError('cannot apply trans effects to Messages')


class TransEffectUnit(TransEffect[None]):

    @property
    def tpe(self) -> Type[Sendable]:
        return type(None)

    def extract(self, data: None, tail: List[TransEffect], in_state: bool) -> Either[R, N]:
        return Lift(TransUnit()) if tail.empty else TransEffectError('cannot apply trans effects to unit')


class TransEffectResult(TransEffect[Any]):

    @property
    def tpe(self) -> Type[Any]:
        return object

    def extract(self, data: object, tail: List[TransEffect], in_state: bool) -> Either[R, N]:
        return Lift(TransResult(data)) if tail.empty else TransEffectError('cannot apply trans effects to result')


class TransEffectDo(TransEffect[TransM]):

    @property
    def tpe(self) -> Type[TransM]:
        return TransM

    def extract(self, data: TransM[A], tail: List[TransEffect], in_state: bool) -> TransStep:
        return Lift(TransDo(data)) if tail.empty else TransEffectError('cannot apply trans effects to TransM')


class TransEffectLog(TransEffect[LogMessage]):

    @property
    def tpe(self) -> Type[LogMessage]:
        return LogMessage

    def extract(self, data: LogMessage, tail: List[TransEffect], in_state: bool) -> TransStep:
        return Lift(TransLog(data)) if tail.empty else TransEffectError('cannot apply trans effects to LogMessage')


__all__ = ()
