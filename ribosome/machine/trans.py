import abc
from typing import Callable, TypeVar, Type, Generic, Awaitable, Any
import functools

from amino import Either, List, Lists, IO, Id, L, _, Maybe, Nil
from amino.state import StateT
from amino.util.string import red, green, ToStr
from amino.dispatch import dispatch_alg
from amino.algebra import AlgebraMeta, Algebra

from ribosome.machine.message_base import (PMessage, default_prio, _machine_attr, _message_attr, _prio_attr, _dyn_attr,
                                           Messages)
from ribosome.data import Data
from ribosome.machine.messages import RunIOAlg, Error, Nop, RunNvimIOAlg, CoroutineAlg
from ribosome.logging import Logging
from ribosome.nvim import NvimIO
from ribosome.machine.transitions import Transitions
from ribosome.machine.transition import Handler, DynHandler, _recover_error
from ribosome.machine.machine import Machine

T = TypeVar('T', bound=Transitions)
D = TypeVar('D', bound=Data)
Mes = TypeVar('Mes', bound=PMessage)
R = TypeVar('R')
N = TypeVar('N')
O = TypeVar('O')
G = TypeVar('G')


class TransAction(Algebra, base=True):

    def __init__(self, messages: List[PMessage]) -> None:
        self.messages = messages


class Transit(Generic[D], TransAction):

    def __init__(self, trans: StateT[Id, D, 'Propagate']) -> None:
        super().__init__(List())
        self.trans = trans

    def _arg_desc(self) -> List[str]:
        return List(str(self.trans))


class Propagate(TransAction):

    @staticmethod
    def one(msg: PMessage) -> TransAction:
        return Propagate(List(msg))

    @staticmethod
    def maybe(msg: Maybe[PMessage]) -> TransAction:
        return Propagate(msg.to_list)

    @staticmethod
    def from_either(res: Either[str, TransAction]) -> TransAction:
        return res.value_or(lambda a: Propagate.one(Error(a)))

    def _arg_desc(self) -> List[str]:
        return self.messages / str


class Unit(TransAction):

    def __init__(self) -> None:
        super().__init__(Nil)

    def _arg_desc(self) -> List[str]:
        return List()


class Result(TransAction):

    def __init__(self, data: Any) -> None:
        self.data = data
        super().__init__(Nil)

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
    def tpe(self) -> Type[Awaitable]:
        return Awaitable

    def extract(self, data: Awaitable, tail: List[TransEffect], in_state: bool) -> Either[R, N]:
        async def coro_map(run: Callable[[R], TransStep]) -> TransStep:
            res = await data
            return lift(run(res), in_state)
        coro = cont(tail, False, coro_map) | data
        return Lift(Propagate.one(CoroutineAlg(coro).pub))


class TransEffectSingleMessage(TransEffect[PMessage]):

    @property
    def tpe(self) -> Type[PMessage]:
        return Messages

    def extract(self, data: PMessage, tail: List[TransEffect], in_state: bool) -> Either[R, N]:
        return Lift(Propagate.one(data)) if tail.empty else TransEffectError('cannot apply trans effects to PMessage')


class TransEffectMessages(TransEffect[List[PMessage]]):

    @property
    def tpe(self) -> Type[List[PMessage]]:
        return List

    def typecheck(self, data: List[PMessage]) -> bool:
        return super().typecheck(data) and data.forall(lambda a: isinstance(a, Messages))

    def extract(self, data: List[PMessage], tail: List[TransEffect], in_state: bool) -> Either[R, N]:
        return Lift(Propagate(data)) if tail.empty else TransEffectError('cannot apply trans effects to Messages')


class TransEffectUnit(TransEffect[None]):

    @property
    def tpe(self) -> Type[PMessage]:
        return type(None)

    def extract(self, data: None, tail: List[TransEffect], in_state: bool) -> Either[R, N]:
        return Lift(Unit()) if tail.empty else TransEffectError('cannot apply trans effects to unit')


class TransEffectResult(TransEffect[Any]):

    @property
    def tpe(self) -> Type[PMessage]:
        return object

    def extract(self, data: object, tail: List[TransEffect], in_state: bool) -> Either[R, N]:
        return Lift(Result(data)) if tail.empty else TransEffectError('cannot apply trans effects to result')


m: TransEffect = TransEffectMaybe()
e: TransEffect = TransEffectEither()
st: TransEffect = TransEffectStateT()
io: TransEffect = TransEffectIO()
nio: TransEffect = TransEffectNvimIO()
coro: TransEffect = TransEffectCoro()
single: TransEffect = TransEffectSingleMessage()
strict: TransEffect = TransEffectMessages()
none: TransEffect = TransEffectUnit()
result: TransEffect = TransEffectResult()


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


def extract(output: O, effects: List[TransEffect]) -> TransAction:
    trans_result = cont(effects, False, lambda f: f(output)) | output
    return lift(trans_result, False)


def decorate(transition, msg_type, prio) -> None:
    setattr(transition, _machine_attr, True)
    setattr(transition, _message_attr, msg_type)
    setattr(transition, _prio_attr, prio)
    setattr(transition, _dyn_attr, False)
    return transition


def message_trans(msg_type: Type[Mes], *effects: TransEffect, prio: float=default_prio
                  ) -> Callable[[Callable[[T], R]], Callable[[T], TransAction]]:
    def add_handler(func: Callable[[T], R]):
        @functools.wraps(func)
        def transition(m, *a) -> TransAction:
            return extract(func(m, *a), Lists.wrap(effects))
        decorate(transition, msg_type, prio)
        return AlgHandler.create(transition)
    return add_handler


def plain(*effects: TransEffect, prio: float=default_prio) -> Callable[[Callable[[T], R]], Callable[[T], TransAction]]:
    return message_trans(None, *effects, prio=prio)


def unit(msg_type: Type[Mes], *effects: TransEffect, prio: float=default_prio
         ) -> Callable[[Callable[[T], R]], Callable[[T], TransAction]]:
    return message_trans(msg_type, *effects, none, prio=prio)


def one(msg_type: Type[Mes], *effects: TransEffect, prio: float=default_prio
        ) -> Callable[[Callable[[T], R]], Callable[[T], TransAction]]:
    return message_trans(msg_type, *effects, single, prio=prio)


def multi(msg_type: Type[Mes], *effects: TransEffect, prio: float=default_prio
          ) -> Callable[[Callable[[T], R]], Callable[[T], TransAction]]:
    return message_trans(msg_type, *effects, strict, prio=prio)


def relay(msg_type: Type[Mes], prio: float=default_prio) -> Callable[[Callable[[T], R]], Callable[[T], TransAction]]:
    def add_handler(func: Callable[[T], R]):
        return decorate(func, msg_type, prio)
    return add_handler


class WrappedHandler(Generic[Mes, D, T], DynHandler[Mes, D]):

    def __init__(self, trans_tpe: Type[T], handler: Handler) -> None:
        self.trans_tpe = trans_tpe
        self.handler = handler

    @staticmethod
    def create(fun: Callable[[Machine, D, Mes], R], tpe: Type[T]) -> 'Handler[Mes, D, DynTrans]':
        return WrappedHandler(tpe, Handler.create(fun))

    def run(self, machine: Machine, data: D, msg: Mes) -> TransAction:
        return _recover_error(self, self.execute(machine, data, msg))

    def execute(self, machine: Machine, data: D, msg: Mes) -> TransAction:
        trans = self.trans_tpe(machine, data, msg)
        return self.handler.fun(trans)

    @property
    def prio(self) -> float:
        return self.handler.prio

    @property
    def dyn(self) -> float:
        return self.handler.dyn

    @property
    def message(self) -> Type[Mes]:
        return self.handler.message

    @property
    def name(self) -> str:
        return self.handler.name

    @property
    def fun(self) -> Callable[[Machine, D, Mes], R]:
        return self.handler.fun


class AlgHandler(Generic[Mes, D], Handler[Mes, D, TransAction]):

    @staticmethod
    def create(fun: Callable[..., R]) -> 'Handler[M, D, R]':
        name, msg, prio, dyn = Handler.attrs(fun)
        return AlgHandler(name, fun, msg, prio, dyn)

    def run(self, machine: Machine, data: D, msg: Mes) -> TransAction:
        ...

    def execute(self, machine: Machine, data: D, msg: Mes) -> TransAction:
        return self.fun(machine, data, msg)

__all__ = ('multi', 'coro', 'single', 'one', 'relay', 'WrappedHandler', 'AlgHandler')
