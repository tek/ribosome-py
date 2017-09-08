import abc
from typing import Callable, TypeVar, Type, Generic, Coroutine
import functools

from amino import Either, List, Lists, IO, Id, L, _, Maybe
from amino.state import IdState, StateT, EitherState
from amino.util.string import red, green, ToStr
from amino.dispatch import dispatch_alg
from amino.algebra import AlgebraMeta, Algebra

from ribosome.machine.message_base import Message, default_prio, _machine_attr, _message_attr, _prio_attr, _dyn_attr
from ribosome.data import Data
from ribosome.machine.messages import RunIOAlg, Error, Nop, RunNvimIOAlg
from ribosome.logging import Logging
from ribosome.nvim import NvimIO
from ribosome.machine.transitions import Transitions

M = TypeVar('M', bound=Transitions)
D = TypeVar('D', bound=Data)
Msg = TypeVar('Msg', bound=Message)
R = TypeVar('R')
N = TypeVar('N')
O = TypeVar('O')
G = TypeVar('G')


class TransAction(Algebra, base=True):

    def __init__(self, messages: List[Message]) -> None:
        self.messages = messages


class Transit(Generic[D], TransAction):

    def __init__(self, trans: StateT[Id, D, 'Propagate']) -> None:
        super().__init__(List())
        self.trans = trans

    def _arg_desc(self) -> List[str]:
        return List(str(self.trans))


class Propagate(TransAction):

    @staticmethod
    def one(msg: Message) -> TransAction:
        return Propagate(List(msg))

    @staticmethod
    def maybe(msg: Maybe[Message]) -> TransAction:
        return Propagate(msg.to_list)

    @staticmethod
    def from_either(res: Either[str, TransAction]) -> TransAction:
        return res.value_or(lambda a: Propagate.one(Error(a)))

    def _arg_desc(self) -> List[str]:
        return self.messages / str


class Unit(TransAction):

    def __init__(self) -> None:
        super().__init__(List())

    def _arg_desc(self) -> List[str]:
        return List()


class TransFailure(TransAction):

    def __init__(self, message: str) -> None:
        super().__init__(List())
        self.message = message

    def _arg_desc(self) -> List[str]:
        return List(self.message)


class TransStep(Generic[R], ToStr, metaclass=AlgebraMeta, base=True):

    def __init__(self, data: R) -> None:
        self.data = data

    @property
    def strict(self) -> bool:
        return isinstance(self, Strict)

    @property
    def error(self) -> bool:
        return isinstance(self, TransEffectError)

    def _arg_desc(self) -> List[str]:
        return List(str(self.data))


class Strict(Generic[R], TransStep[R]):
    pass


class Lift(Generic[R], TransStep[R]):
    pass


class TransEffectError(TransStep[str]):
    pass


class TransEffect(Generic[R], abc.ABC, Logging):

    @abc.abstractproperty
    def tpe(self) -> Type[R]:
        ...

    @abc.abstractmethod
    def extract(self, data: R, tail: List['TransEffect'], in_state: bool) -> TransStep:
        ...

    def run(self, data: R, tail: List['TransEffect'], in_state: bool) -> TransStep:
        return (
            self.extract(data, tail, in_state)
            if isinstance(data, self.tpe) else
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


class TransEffectIdState(Generic[D, R], TransEffectStateT[Id, D, R]):

    @property
    def tpe(self) -> Type[IdState[D, R]]:
        return IdState

    def extract(self, data: IdState, tail: List[TransEffect], in_state: bool) -> IdState:
        return (
            TransEffectError('cannot nest `State` in transition result')
            if in_state else
            Strict(cont(tail, True, lambda run: data.map(lambda inner: self.check(run(inner)))) | data)
        )


class TransEffectEitherState(Generic[D, R], TransEffectStateT[Either, D, R]):

    @property
    def tpe(self) -> Type[EitherState[D, R]]:
        return EitherState

    def extract(self, data: EitherState[D, R], tail: List[TransEffect], in_state: bool) -> IdState:
        return (
            TransEffectError('cannot nest `State` in transition result')
            if in_state else
            Strict(cont(tail, True, lambda run: data.map(lambda inner: self.check(run(inner)))) | data)
        )


class TransEffectIO(Generic[R], TransEffect[IO[R]]):

    @property
    def tpe(self) -> Type[IO[R]]:
        return IO

    def extract(self, data: IO[R], tail: List[TransEffect], in_state: bool) -> Either[R, N]:
        io = cont(tail, False, data.map) | data
        return Lift(Propagate.one(RunIOAlg(io.map(L(lift)(_, in_state)))))


class TransEffectNvimIO(Generic[R], TransEffect[NvimIO[R]]):

    @property
    def tpe(self) -> Type[NvimIO[R]]:
        return NvimIO

    def extract(self, data: NvimIO[R], tail: List[TransEffect], in_state: bool) -> Either[R, N]:
        io = cont(tail, False, data.map) | data
        return Lift(Propagate.one(RunNvimIOAlg(io.map(L(lift)(_, in_state)))))


class TransEffectCoro(TransEffect):

    @property
    def tpe(self) -> Type[Coroutine]:
        return Coroutine

    def extract(self, data: IO[R], tail: List[TransEffect], in_state: bool) -> Either[R, N]:
        ...


class TransEffectSingleMessage(TransEffect[Message]):

    @property
    def tpe(self) -> Type[Message]:
        return Message

    def extract(self, data: Message, tail: List[TransEffect], in_state: bool) -> Either[R, N]:
        return Lift(Propagate.one(data)) if tail.empty else TransEffectError('cannot apply trans effects to Message')


class TransEffectMessages(TransEffect[List[Message]]):

    @property
    def tpe(self) -> Type[List[Message]]:
        return List

    def extract(self, data: List[Message], tail: List[TransEffect], in_state: bool) -> Either[R, N]:
        return Lift(Propagate(data)) if tail.empty else TransEffectError('cannot apply trans effects to Messages')


class TransEffectUnit(TransEffect[None]):

    @property
    def tpe(self) -> Type[Message]:
        return type(None)

    def extract(self, data: Message, tail: List[TransEffect], in_state: bool) -> Either[R, N]:
        return Lift(Unit()) if tail.empty else TransEffectError('cannot apply trans effects to unit')


m: TransEffect = TransEffectMaybe()
e: TransEffect = TransEffectEither()
st: TransEffect = TransEffectIdState()
est: TransEffect = TransEffectEitherState()
io: TransEffect = TransEffectIO()
nio: TransEffect = TransEffectNvimIO()
coro: TransEffect = TransEffectCoro()
single: TransEffect = TransEffectSingleMessage()
strict: TransEffect = TransEffectMessages()
none: TransEffect = TransEffectUnit()


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
            TransFailure(f'transition did not produce `TransAction`: {{red(res)}}')
        )


_lifter = Lifter()
lift = dispatch_alg(_lifter, TransStep, 'lift_', _lifter.lift_res)


def extract(output: O, effects: List[TransEffect]) -> TransAction:
    trans_result = cont(effects, False, lambda f: f(output)) | output
    return lift(trans_result, False)


def decorate(transition, msg_type, prio) -> None:
    setattr(transition, _machine_attr, True)
    setattr(transition, _message_attr, msg_type)
    setattr(transition, _prio_attr, prio)
    setattr(transition, _dyn_attr, False)
    return transition


def base(msg_type: Type[Msg], *effects: TransEffect, prio: float=default_prio
         ) -> Callable[[Callable[[M], R]], Callable[[M], TransAction]]:
    def add_handler(func: Callable[[M], R]):
        @functools.wraps(func)
        def transition(m, *a) -> TransAction:
            return extract(func(m, *a), Lists.wrap(effects))
        return decorate(transition, msg_type, prio)
    return add_handler


def unit(msg_type: Type[Msg], *effects: TransEffect, prio: float=default_prio
         ) -> Callable[[Callable[[M], R]], Callable[[M], TransAction]]:
    return base(msg_type, *effects, none, prio=prio)


def one(msg_type: Type[Msg], *effects: TransEffect, prio: float=default_prio
        ) -> Callable[[Callable[[M], R]], Callable[[M], TransAction]]:
    return base(msg_type, *effects, single, prio=prio)


def multi(msg_type: Type[Msg], *effects: TransEffect, prio: float=default_prio
          ) -> Callable[[Callable[[M], R]], Callable[[M], TransAction]]:
    return base(msg_type, *effects, strict, prio=prio)


def relay(msg_type: Type[Msg], prio: float=default_prio) -> Callable[[Callable[[M], R]], Callable[[M], TransAction]]:
    def add_handler(func: Callable[[M], R]):
        return decorate(func, msg_type, prio)
    return add_handler

__all__ = ('multi', 'coro', 'single', 'one', 'relay')
