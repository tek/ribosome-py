import abc
from typing import TypeVar, Generic, Union

from amino import Maybe, List, __, Nil, Either, L, _
from amino.state import StateT, MaybeState, EitherState, IdState
from amino.id import Id
from amino.dispatch import dispatch_alg
from amino.tc.base import TypeClass, F
from amino.string.hues import blue

from ribosome.logging import Logging
from ribosome.nvim.io import NvimIOState, NS
from ribosome.nvim import NvimIO
from ribosome.dispatch.data import (DispatchResult, DispatchUnit, DispatchError, DispatchReturn, DispatchIO, DIO,
                                    DispatchDo)
from ribosome.trans.action import (Transit, Propagate, TransUnit, TransResult, TransFailure, TransAction, TransIO,
                                   TransDo)
from ribosome.trans.message_base import Message
from ribosome.trans.handler import TransComplete


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


class TransValidator(Logging):

    def __init__(self, name: str) -> None:
        self.name = name

    def failure(self, error: Union[str, Exception]) -> NvimIOState[D, DispatchResult]:
        return NvimIOState.pure(DispatchResult(DispatchError.cons(f'trans {blue(self.name)}: {error}'), Nil))

    def validate_transit(self, action: Transit) -> NvimIOState[D, DispatchResult]:
        def loop(tts: TransformTransState) -> NS[D, DispatchResult]:
            return tts.run(action.trans).map(L(TransComplete)(self.name, _)).flat_map(validate_trans_action)
        return (
            TransformTransState.e_for(action.trans)
            .map(loop)
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

    def validate_trans_do(self, action: TransDo) -> NvimIOState[D, DispatchResult]:
        return NvimIOState.pure(DispatchResult(DispatchDo(action), Nil))


def validate_trans_action(tc: TransComplete) -> NS[D, DispatchResult]:
    val = dispatch_alg(TransValidator(tc.name), TransAction, 'validate_')
    return val(tc.action)

__all__ = ('validate_trans_action',)
