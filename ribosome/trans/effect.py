import abc
from typing import Callable, TypeVar, Type, Generic, Awaitable, Any

from amino import Either, List, IO, L, _, Maybe
from amino.state import StateT
from amino.util.string import red, green
from amino.dispatch import dispatch_alg

from ribosome.logging import Logging
from ribosome.nvim import NvimIO
from ribosome.trans.action import (TransStep, TransEffectError, Lift, Propagate, Strict, TransUnit, TransResult,
                                   TransAction, Transit, TransFailure, TransIO)
from ribosome.trans.message_base import Sendable, Messages
from ribosome.trans.messages import Error, Nop, CoroutineAlg

D = TypeVar('D')
R = TypeVar('R')
N = TypeVar('N')
G = TypeVar('G')


class TransEffect(Generic[R], abc.ABC, Logging):

    @abc.abstractproperty
    def tpe(self) -> Type[R]:
        ...

    @abc.abstractmethod
    def extract(self, data: R, tail: List['TransEffect'], in_state: bool) -> TransStep:
        ...

    def typecheck(self, data: R) -> bool:
        return isinstance(data, self.tpe)

    def run(self, data: R, tail: List['TransEffect'], in_state: bool) -> TransStep:
        return (
            self.extract(data, tail, in_state)
            if self.typecheck(data) else
            TransEffectError(f'result {red(data)} does not have type {green(self.tpe.__qualname__)}')
        )


def cont(tail: List[TransEffect], in_state: bool, f: Callable[[Callable[[R], TransStep]], TransStep]
         ) -> Maybe[TransStep]:
    return tail.detach_head.map2(lambda h, t: f(lambda a: h.run(a, t, in_state)))


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
        return Lift(nested.value_or(L(Error)(_) >> Propagate.one))


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
        return Lift(TransIO(io.map(L(lift)(_, in_state))))


class TransEffectNvimIO(Generic[R], TransEffect[NvimIO[R]]):

    @property
    def tpe(self) -> Type[NvimIO[R]]:
        return NvimIO

    def extract(self, data: NvimIO[R], tail: List[TransEffect], in_state: bool) -> TransStep:
        io = cont(tail, False, data.map) | data
        return Lift(TransIO(io.map(L(lift)(_, in_state))))


class TransEffectCoro(TransEffect):

    @property
    def tpe(self) -> Type[Awaitable]:
        return Awaitable

    def extract(self, data: Awaitable, tail: List[TransEffect], in_state: bool) -> Either[R, N]:
        async def coro_map(run: Callable[[R], TransStep]) -> TransStep:
            res = await data
            return lift(run(res), in_state)
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
    def tpe(self) -> Type[Sendable]:
        return object

    def extract(self, data: object, tail: List[TransEffect], in_state: bool) -> Either[R, N]:
        return Lift(TransResult(data)) if tail.empty else TransEffectError('cannot apply trans effects to result')


class Lifter(Logging):

    def lift_lift(self, res: Lift, in_state: bool) -> TransAction:
        return lift(res.data, in_state)

    def lift_strict(self, res: Strict, in_state: bool) -> TransAction:
        return Transit(res.data / L(lift)(_, True))

    def lift_trans_effect_error(self, res: TransEffectError, in_state: bool) -> TransAction:
        return TransFailure(res.data)

    def lift_res(self, res: R, in_state: bool) -> TransAction:
        return (
            res
            if isinstance(res, TransAction) else
            TransFailure(f'transition did not produce `TransAction`: {red(res)}')
        )


_lifter = Lifter()
lift = dispatch_alg(_lifter, TransStep, 'lift_', _lifter.lift_res)

__all__ = ('TransEffect', 'lift')
