import abc
import time
from typing import Any, TypeVar, Generic, Union

import amino
from amino import Maybe, _, List, Map, L, __, Nil, Either
from amino.state import StateT, MaybeState, EitherState, IdState
from amino.id import Id
from amino.util.string import blue, ToStr
from amino.dispatch import dispatch_alg
from amino.tc.base import TypeClass, F
from amino.dat import Dat

from ribosome.logging import Logging
from ribosome.nvim.io import NvimIOState
from ribosome.nvim import NvimIO
from ribosome.dispatch.data import DispatchResult, DispatchUnit, DispatchError, DispatchReturn, DispatchIO, DIO
from ribosome.trans.action import Transit, Propagate, TransUnit, TransResult, TransFailure, TransAction, TransIO
from ribosome.trans.message_base import Message
from ribosome.trans.legacy import Handler, TransitionFailed


class Handlers(Dat['Handlers']):

    def __init__(self, prio: int, handlers: Map[type, Handler]) -> None:
        self.prio = prio
        self.handlers = handlers

    def handler(self, msg):
        return self.handlers.get(type(msg))


D = TypeVar('D')
R = TypeVar('R')
G = TypeVar('G', bound=F)
I = TypeVar('I')


class TransformTransState(Generic[G], TypeClass):

    @abc.abstractmethod
    def transform(self, st: StateT[G, D, DispatchResult]) -> NvimIOState[D, DispatchResult]:
        ...

    def run(self, st: StateT[G, D, List[Message]]) -> NvimIOState[D, DispatchResult]:
        return self.transform(st)


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
            .map(__.run(action.trans))
            .map(__.flat_map(self.validate))
            .value_or(self.failure)
        )

    def validate_propagate(self, action: Propagate) -> NvimIOState[D, DispatchResult]:
        return NvimIOState.pure(DispatchResult(DispatchUnit(), action.messages))

    def validate_trans_unit(self, action: TransUnit) -> NvimIOState[D, DispatchResult]:
        return NvimIOState.pure(DispatchResult(DispatchUnit(), action.messages))

    def validate_trans_result(self, action: TransResult) -> NvimIOState[D, DispatchResult]:
        return NvimIOState.pure(DispatchResult(DispatchReturn(action.data), Nil))

    def validate_trans_failure(self, action: TransFailure) -> NvimIOState[D, DispatchResult]:
        return self.failure(action.message)

    def validate_trans_io(self, action: TransIO[I]) -> NvimIOState[D, DispatchResult]:
        output = DIO.cons(action.io).cata(DispatchError.cons, DispatchIO)
        return NvimIOState.pure(DispatchResult(output, Nil))


class HandlerJob(Generic[D], Logging, ToStr):

    def __init__(self, name: str, handler: Handler, msg: Message) -> None:
        if not isinstance(handler, Handler):
            raise 1
        self.name = name
        self.msg = msg
        self.handler = handler
        self.start_time = time.time()

    @staticmethod
    def from_handler(name: str, handler: Handler, msg: Message) -> 'HandlerJob[M, D]':
        return AlgHandlerJob(name, handler, msg)

    @abc.abstractmethod
    def run(self) -> Any:
        ...

    @property
    def trans_desc(self) -> str:
        return blue(f'{self.name}.{self.handler.name}')

    def _arg_desc(self) -> List[str]:
        return List(str(self.msg))


class AlgHandlerJob(HandlerJob):

    def run(self) -> NvimIOState[D, DispatchResult]:
        try:
            r = self.handler.run(self.msg)
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


__all__ = ('Handlers', 'HandlerJob', 'AlgHandlerJob')
