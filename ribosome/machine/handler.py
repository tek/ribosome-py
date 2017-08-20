import abc
import time
from typing import Any, Sequence, TypeVar, Generic, Type, Callable, Tuple
import asyncio

import amino
from amino import Maybe, _, List, Map, Just
from amino.task import Task
from amino.state import StateT, EvalState, MaybeState, EitherState, IdState
from amino.tc.optional import Optional
from amino.id import Id
from amino.util.string import blue
from amino.dispatch import dispatch_alg

from ribosome.logging import Logging
from ribosome.machine.message_base import Message, Publish
from ribosome.machine.transition import (Handler, TransitionResult, CoroTransitionResult, StrictTransitionResult,
                                         TransitionFailed, Coroutine, MachineError, Error)
from ribosome.machine.messages import RunTask, UnitTask, DataTask, Nop
from ribosome.machine.interface import MachineI
from ribosome.data import Data
from ribosome.machine.trans import TransAction, Transit, Propagate


def is_seq(a):
    return isinstance(a, Sequence)


def is_message(a):
    return isinstance(a, Message)


class Handlers(Logging):

    def __init__(self, prio: int, handlers: Map[type, Handler]) -> None:
        self.prio = prio
        self.handlers = handlers

    def handler(self, msg):
        return self.handlers.get(type(msg))


M = TypeVar('M', bound=MachineI)
D = TypeVar('D', bound=Data)
Msg = TypeVar('Msg', bound=Message)
R = TypeVar('R')


def create_result(data: D, msgs: List[Message]) -> TransitionResult:
    pub, resend = msgs.split_type(Publish)
    pub_msgs = pub.map(_.message)
    return StrictTransitionResult(data=data, pub=pub_msgs, resend=resend)


class HandlerJob(Generic[M, D], Logging):

    def __init__(self, machine: M, data: D, msg: Message, handler: Handler, data_type: Type[D]) -> None:
        self.machine = machine
        self.data = data
        self.msg = msg
        self.handler = handler
        self.data_type = data_type
        self.start_time = time.time()

    @abc.abstractmethod
    def run(self) -> TransitionResult:
        ...

    @property
    def trans_desc(self) -> str:
        return blue(f'{self.machine.title}.{self.handler.name}')


class DynHandlerJob(HandlerJob):

    def run(self) -> TransitionResult:
        result = self._execute_transition(self.handler, self.data, self.msg)
        return self.dispatch_transition_result(result)

    def _execute_transition(self, handler, data, msg):
        try:
            return handler.run(data, msg)
        except TransitionFailed as e:
            raise
        except Exception as e:
            return self.handle_transition_error(e)

    def handle_transition_error(self, e):
        if amino.development:
            err = 'transition "{}" failed for {} in {}'
            self.log.caught_exception(err.format(self.handler.name, self.msg, self.machine.title), e)
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
        msgs, rest = trans.split_type(Message)
        if rest:
            tpl = 'invalid transition result parts for {} in {}: {}'
            msg = tpl.format(self.msg, self.machine.title, rest)
            if amino.development:
                raise MachineError(msg)
            else:
                self.log.error(msg)
        new_data = datas.head | self.data
        return create_result(new_data, msgs)

    def transform_result(self, result):
        if asyncio.iscoroutine(result) or isinstance(result, asyncio.futures.Future):
            return Coroutine(result).pub
        elif isinstance(result, Task):
            return RunTask(result, Just(self.msg))
        elif isinstance(result, RunTask):
            return RunTask(result.task, Just(self.msg))
        elif isinstance(result, UnitTask):
            return UnitTask(result.task, Just(self.msg))
        elif isinstance(result, DataTask):
            return DataTask(result.cons, Just(self.msg))
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


class AlgResultValidator(Generic[D], Logging):

    def __init__(self, data: D) -> None:
        self.data = data

    def validate(self, trans: TransAction) -> TransitionResult:
        new_state, result = self.transit(trans)
        return create_result(new_state, result)

    @property
    def transit(self) -> Callable[[TransAction], Tuple[D, List[Message]]]:
        return dispatch_alg(self, TransAction, 'transit_')

    def transit_transit(self, action: Transit) -> Tuple[D, List[Message]]:
        new_state, result = action.trans.run(self.data).value
        return new_state, result.messages

    def transit_propagate(self, action: Propagate) -> Tuple[D, List[Message]]:
        return self.data, action.messages


class AlgHandlerJob(HandlerJob):

    def run(self) -> TransitionResult:
        try:
            r = self.handler.execute(self.data, self.msg)
        except Exception as e:
            return self.exception(e)
        else:
            return AlgResultValidator(self.data).validate(r)

    def exception(self, e: Exception) -> StateT[Id, D, R]:
        if amino.development:
            err = f'transitioning {self.trans_desc}'
            self.log.caught_exception(err, e)
            raise TransitionFailed(str(e)) from e
        return TransitionResult.failed(self.data, f'{self.trans_desc}: {msg}')

__all__ = ('Handlers', 'HandlerJob', 'AlgHandlerJob', 'DynHandlerJob')
