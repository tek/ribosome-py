import abc
from typing import Callable, TypeVar, Type, Generic, Coroutine
import functools

from amino import Either, List, Lists, IO, Id, L, _, Maybe
from amino.state import IdState, StateT
from amino.util.string import red, green, ToStr
from amino.dispatch import dispatch_alg
from amino.algebra import AlgebraMeta, Algebra

from ribosome.machine.message_base import Message, default_prio, _machine_attr, _message_attr, _prio_attr, _dyn_attr
from ribosome.data import Data
from ribosome.machine.interface import MachineI
from ribosome.machine.messages import RunIOAlg, Error
from ribosome.logging import Logging

M = TypeVar('M', bound=MachineI)
D = TypeVar('D', bound=Data)
Msg = TypeVar('Msg', bound=Message)
R = TypeVar('R')
N = TypeVar('N')
O = TypeVar('O')
E = TypeVar('E')


class TransAction(Algebra, base=True):
    pass


class Transit(Generic[D], TransAction):

    def __init__(self, trans: StateT[Id, D, 'Propagate']) -> None:
        self.trans = trans

    def _arg_desc(self) -> List[str]:
        return List(str(self.trans))


class Propagate(TransAction):

    @staticmethod
    def one(msg: Message) -> TransAction:
        return Propagate(List(msg))

    def __init__(self, messages: List[Message]) -> None:
        self.messages = messages

    def _arg_desc(self) -> List[str]:
        return self.messages / str


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
            TransEffectError(f'invalid type: {red(data)} / {green(self.tpe)}')
        )


def cont(tail: List[TransEffect], in_state: bool, f: Callable[[Callable[[R], TransStep]], TransStep]
         ) -> Maybe[TransStep]:
    return tail.detach_head.map2(lambda h, t: f(lambda a: h.run(a, t, in_state)))


class TransEffectEither(Generic[R], TransEffect[Either[str, R]]):

    @property
    def tpe(self) -> Type[Either[str, R]]:
        return Either

    def extract(self, data: Either[R, N], tail: List[TransEffect], in_state: bool) -> TransStep:
        nested = data.map(lambda a: cont(tail, in_state, lambda run: Lift(run(a))) | a)
        return Lift(nested.value_or(L(Error)(_) >> Propagate.one))


class TransEffectIdState(TransEffect):

    @property
    def tpe(self) -> Type[StateT[Id, D, R]]:
        return StateT

    def extract(self, data: IdState, tail: List[TransEffect], in_state: bool) -> IdState:
        def check(result: TransEffect[R]) -> None:
            return (
                Propagate.one(f'`State` trans result `{result}` is not a `TransStep`')
                if not isinstance(result, TransStep) else
                Propagate.one(Error('found nested `State` in transition result'))
                if result.strict else
                Propagate.one(Error(result.data))
                if result.error else
                result.data
            )

        return (
            TransEffectError('cannot nest `State` in transition result')
            if in_state else
            Strict(cont(tail, True, lambda run: data.map(lambda inner: check(run(inner)))) | data)
        )


class TransEffectIO(Generic[R], TransEffect[IO[R]]):

    @property
    def tpe(self) -> Type[IO[R]]:
        return IO

    def extract(self, data: IO[R], tail: List[TransEffect], in_state: bool) -> Either[R, N]:
        io = cont(tail, False, data.map) | data
        return Lift(Propagate.one(RunIOAlg(io.map(lift))))


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


e = TransEffectEither()
st = TransEffectIdState()
io = TransEffectIO()
coro = TransEffectCoro()
single = TransEffectSingleMessage()


class Lifter(Logging):

    def lift_lift(self, res: Lift) -> TransAction:
        return lift(res.data)

    def lift_strict(self, res: Strict) -> TransAction:
        return Transit(res.data / lift)

    def lift_trans_effect_error(self, res: TransEffectError) -> TransAction:
        return Transit(IdState.pure(Propagate.one(Error(res.data))))

    def lift_res(self, res: R) -> R:
        return res


_lifter = Lifter()
lift = dispatch_alg(_lifter, TransStep, 'lift_', _lifter.lift_res)


def extract(output: O, effects: List[TransEffect]) -> TransAction:
    trans_result = cont(effects, False, lambda f: f(output)) | output
    return lift(trans_result)


def decorate(transition, msg_type, prio) -> None:
    setattr(transition, _machine_attr, True)
    setattr(transition, _message_attr, msg_type)
    setattr(transition, _prio_attr, prio)
    setattr(transition, _dyn_attr, False)
    return transition


def multi(msg_type: Type[Msg], *effects: TransEffect, prio: float=default_prio
          ) -> Callable[[Callable[[M], R]], Callable[[M], TransAction]]:
    def add_handler(func: Callable[[M], R]):
        @functools.wraps(func)
        def transition(m, *a) -> None:
            return extract(func(m, *a), Lists.wrap(effects))
        return decorate(transition, msg_type, prio)
    return add_handler


def one(msg_type: Type[Msg], *effects: TransEffect, prio: float=default_prio
        ) -> Callable[[Callable[[M], R]], Callable[[M], TransAction]]:
    return multi(msg_type, *effects, single, prio=prio)


def relay(msg_type: Type[Msg], prio: float=default_prio) -> Callable[[Callable[[M], R]], Callable[[M], TransAction]]:
    def add_handler(func: Callable[[M], R]):
        return decorate(func, msg_type, prio)
    return add_handler

__all__ = ('multi', 'e', 'st', 'io', 'coro', 'single', 'one', 'relay')
