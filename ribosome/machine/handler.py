import abc
import time
from typing import Any, Sequence, TypeVar, Generic, Type, Union
import asyncio

import amino
from amino import Maybe, _, List, Map, Just, L, __, Nil, Nothing, Either
from amino.io import IO
from amino.state import StateT, EvalState, MaybeState, EitherState, IdState
from amino.tc.optional import Optional
from amino.id import Id
from amino.util.string import blue, ToStr
from amino.dispatch import dispatch_alg
from amino.tc.base import TypeClass, F
from amino.dat import Dat

from ribosome.logging import Logging
from ribosome.machine.message_base import Message, Publish, Envelope, Messages
from ribosome.machine.transition import (Handler, TransitionResult, CoroTransitionResult, StrictTransitionResult,
                                         TransitionFailed, Coroutine, MachineError, Error)
from ribosome.machine.messages import RunIO, UnitIO, DataIO, Nop
from ribosome.machine.machine import Machine
from ribosome.data import Data
from ribosome.machine.trans import TransAction, Transit, Propagate, Unit, TransFailure, Result
from ribosome.nvim.io import NvimIOState
from ribosome.nvim import NvimIO
from ribosome.request.dispatch.data import DispatchResult, DispatchUnit, DispatchError, DispatchReturn


def is_seq(a):
    return isinstance(a, Sequence)


def is_message(a):
    return isinstance(a, Message)


class Handlers(Dat['Handlers']):

    def __init__(self, prio: int, handlers: Map[type, Handler]) -> None:
        self.prio = prio
        self.handlers = handlers

    def handler(self, msg):
        return self.handlers.get(type(msg))


M = TypeVar('M', bound=Machine)
D = TypeVar('D', bound=Data)
R = TypeVar('R')


def create_result(data: D, msgs: List[Message], output: Maybe[Any]=Nothing) -> TransitionResult:
    publ, resend = msgs.split_type((Publish, Envelope))
    env, pub = publ.split_type(Envelope)
    pub_msgs = env + pub.map(_.message)
    return StrictTransitionResult(data=data, pub=pub_msgs, resend=resend, output=output)


def create_failure(data: D, desc: str, error: Union[str, Exception]) -> TransitionResult:
    return (
        TransitionResult.failed(data, error)
        if isinstance(error, Exception) else
        TransitionResult.failed(data, f'{desc}: {error}')
    )


class HandlerJob(Generic[D], Logging, ToStr):

    def __init__(self, name: str, handler: Handler, data: D, msg: Message, data_type: Type[D]) -> None:
        if not isinstance(handler, Handler):
            raise 1
        self.name = name
        self.data = data
        self.msg = msg
        self.handler = handler
        self.data_type = data_type
        self.start_time = time.time()

    @staticmethod
    def from_handler(name: str, handler: Handler, data: D, msg: Message) -> 'HandlerJob[M, D]':
        tpe = DynHandlerJob if handler.dyn else AlgHandlerJob
        return tpe(name, handler, data, msg, type(data))

    @abc.abstractmethod
    def run(self) -> TransitionResult:
        ...

    @property
    def trans_desc(self) -> str:
        return blue(f'{self.name}.{self.handler.name}')

    def _arg_desc(self) -> List[str]:
        return List(str(self.msg))


class DynHandlerJob(HandlerJob):

    def run(self) -> TransitionResult:
        result = self._execute_transition(self.handler, self.data, self.msg)
        return self.dispatch_transition_result(result)

    def _execute_transition(self, handler, data, msg):
        try:
            return handler.run(self, data, msg)
        except TransitionFailed as e:
            raise
        except Exception as e:
            return self.handle_transition_error(e)

    def handle_transition_error(self, e):
        if amino.development:
            err = 'transition "{}" failed for {} in {}'
            self.log.caught_exception(err.format(self.handler.name, self.msg, self.name), e)
            raise TransitionFailed(str(e)) from e
        return self.failure_result(str(e))

    def failure_result(self, err: str) -> Maybe[StrictTransitionResult]:
        return Just(TransitionResult.failed(self.data, err))

    def dispatch_transition_result(self, result):
        return (
            result /
            self.process_result |
            TransitionResult.empty(self.data)
        )

    def process_result(self, res0: Any) -> TransitionResult:
        if isinstance(res0, Coroutine):
            return CoroTransitionResult(data=self.data, coro=res0)
        elif isinstance(res0, TransitionResult):
            return res0
        elif isinstance(res0, self.data_type):
            return TransitionResult.empty(res0)
        elif isinstance(res0, StateT):
            result = self.transform_state(res0)
        elif is_message(res0) or not is_seq(res0):
            result = List(res0)
        else:
            result = res0
        datas, rest = List.wrap(result).split_type(self.data_type)
        trans = rest / self.transform_result
        msgs, rest = trans.split_type(Messages)
        if rest:
            tpl = 'invalid transition result parts for {} in {}: {}'
            msg = tpl.format(self.msg, self.name, rest)
            if amino.development:
                raise MachineError(msg)
            else:
                self.log.error(msg)
        new_data = datas.head | self.data
        return create_result(new_data, msgs)

    def transform_result(self, result):
        if asyncio.iscoroutine(result) or isinstance(result, asyncio.futures.Future):
            return Coroutine(result).pub
        elif isinstance(result, IO):
            return RunIO(result, Just(self.msg))
        elif isinstance(result, RunIO):
            return RunIO(result.io, Just(self.msg))
        elif isinstance(result, UnitIO):
            return UnitIO(result.io, Just(self.msg))
        elif isinstance(result, DataIO):
            return DataIO(result.cons, Just(self.msg))
        else:
            return result

    def transform_state(self, res0: StateT):
        res1 = res0.run(self.data)
        if isinstance(res0, EvalState):
            (data, result) = res1._value()
        elif isinstance(res0, MaybeState):
            (data, result) = res1.get_or_else((self.data, Nop()))
        elif isinstance(res0, EitherState):
            (data, result) = res1.value_or(lambda a: (self.data, Error(str(a))))
        elif isinstance(res0, IdState):
            (data, result) = res1.value
        else:
            return List(Error(f'invalid effect for transition result `State`: {res0.tpe}#{res1}'))
        r2 = (
            Nop()
            if result is None else
            result.get_or_else(Nop())
            if Optional.exists(type(result)) else
            result
        )
        return (
            r2.cons(data)
            if isinstance(r2, List) else
            List(data, r2)
        )


A = TypeVar('A')
G = TypeVar('G', bound=F)


class TransformTransState(Generic[G], TypeClass):

    @abc.abstractmethod
    def transform(self, st: StateT[G, D, DispatchResult]) -> NvimIOState[D, DispatchResult]:
        ...

    def run(self, st: StateT[G, D, List[Message]]) -> NvimIOState[D, DispatchResult]:
        return self.transform(self.result(st))

    def result(self, st: StateT[G, D, List[Message]]) -> StateT[F, D, DispatchResult]:
        return st / L(DispatchResult)(DispatchUnit(), _)


class TransformIdState(TransformTransState[Id], tpe=IdState):

    def transform(self, st: IdState[D, DispatchResult]) -> NvimIOState[D, DispatchResult]:
        return NvimIOState.from_id(st)


class TransformMaybeState(TransformTransState[Maybe], tpe=MaybeState):

    def transform(self, st: MaybeState[D, DispatchResult]) -> NvimIOState[D, DispatchResult]:
        return NvimIOState.apply(lambda s: NvimIO.pure(st.run(s) | (s, DispatchResult(DispatchUnit(), Nil))))


class TransformEitherState(TransformTransState[Either], tpe=EitherState):

    def transform(self, st: EitherState[D, DispatchResult]) -> NvimIOState[D, DispatchResult]:
        return NvimIOState.apply(
            lambda s: NvimIO.pure(st.run(s).value_or(lambda err: (s, DispatchResult(DispatchError.cons(err), Nil))))
        )


class TransformNvimIOState(TransformTransState[NvimIO], tpe=NvimIOState):

    def transform(self, st: NvimIOState[D, DispatchResult]) -> NvimIOState[D, DispatchResult]:
        return st


# StateT[D, List[Message]] -> ? -> StateT[D, DispatchResult] -> NvimIOState[D, DispatchResult] ->
# NvimIOState[PluginState, DispatchResult] -> NvimIO[Any]

class AlgResultValidator(Logging):

    def __init__(self, desc: str) -> None:
        self.desc = desc

    @property
    def validate(self) -> NvimIOState[D, DispatchResult]:
        return dispatch_alg(self, TransAction, 'validate_')

    def failure(self, error: Union[str, Exception]) -> NvimIOState[D, DispatchResult]:
        return NvimIOState.pure(DispatchResult(DispatchError.cons(error), Nil))

    def validate_transit(self, action: Transit) -> NvimIOState[D, DispatchResult]:
        return (
            TransformTransState.e_for(action.trans)
            .flat_map(__.run(action.trans))
            .value_or(self.failure)
        )

    def validate_propagate(self, action: Propagate) -> NvimIOState[D, DispatchResult]:
        return NvimIOState.pure(DispatchResult(DispatchUnit(), action.messages))

    def validate_unit(self, action: Unit) -> NvimIOState[D, DispatchResult]:
        return NvimIOState.pure(DispatchResult(DispatchUnit(), action.messages))

    def validate_result(self, action: Result) -> NvimIOState[D, DispatchResult]:
        return NvimIOState.pure(DispatchResult(DispatchReturn(action.data), Nil))

    def validate_trans_failure(self, action: TransFailure) -> NvimIOState[D, DispatchResult]:
        return self.failure(action.message)


class AlgHandlerJob(HandlerJob):

    def run(self, machine=None) -> NvimIOState[D, DispatchResult]:
        try:
            r = self.handler.execute(machine, self.data, self.msg)
        except Exception as e:
            return self.exception(e)
        else:
            return AlgResultValidator(self.trans_desc).validate(r)

    def exception(self, e: Exception) -> StateT[Id, D, R]:
        if amino.development:
            err = f'transitioning {self.trans_desc}'
            self.log.caught_exception(err, e)
            raise TransitionFailed(str(e)) from e
        return NvimIOState.pure(DispatchResult(DispatchError.cons(e), Nil))

__all__ = ('Handlers', 'HandlerJob', 'AlgHandlerJob', 'DynHandlerJob')
