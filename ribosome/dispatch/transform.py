import abc
from typing import TypeVar, Generic, Union

from amino import Maybe, Nil, Either, L, _
from amino.state import StateT, MaybeState, EitherState, IdState
from amino.id import Id
from amino.dispatch import dispatch_alg
from amino.tc.base import TypeClass, F
from amino.string.hues import blue

from ribosome.logging import Logging
from ribosome.nvim.io import NvimIOState, NS
from ribosome.nvim import NvimIO
from ribosome.dispatch.data import (DispatchResult, DispatchUnit, DispatchError, DispatchReturn, DispatchIO, DIO,
                                    DispatchDo, DispatchLog)
from ribosome.trans.action import (Transit, Propagate, TransUnit, TransResult, TransFailure, TransAction, TransIO,
                                   TransDo, TransLog)
from ribosome.trans.run import TransComplete


D = TypeVar('D')
R = TypeVar('R')
G = TypeVar('G', bound=F)
I = TypeVar('I')


class TransformTransState(Generic[G], TypeClass):

    @abc.abstractmethod
    def run(self, st: StateT[G, D, DispatchResult]) -> NvimIOState[D, DispatchResult]:
        ...


class TransformIdState(TransformTransState[Id], tpe=IdState):

    def run(self, st: IdState[D, DispatchResult]) -> NvimIOState[D, DispatchResult]:
        return NvimIOState.from_id(st)


class TransformMaybeState(TransformTransState[Maybe], tpe=MaybeState):

    def run(self, st: MaybeState[D, DispatchResult]) -> NvimIOState[D, DispatchResult]:
        return NvimIOState.apply(lambda s: NvimIO.pure(st.run(s) | (s, TransUnit())))


class TransformEitherState(TransformTransState[Either], tpe=EitherState):

    def run(self, st: EitherState[D, DispatchResult]) -> NvimIOState[D, DispatchResult]:
        return NvimIOState.apply(
            lambda s: NvimIO.pure(st.run(s).value_or(lambda err: (s, TransFailure(err))))
        )


class TransformNvimIOState(TransformTransState[NvimIO], tpe=NvimIOState):

    def run(self, st: NvimIOState[D, DispatchResult]) -> NvimIOState[D, DispatchResult]:
        return st


class TransValidator(Logging):

    def __init__(self, name: str) -> None:
        self.name = name

    def failure(self, error: Union[str, Exception]) -> NvimIOState[D, DispatchResult]:
        return NvimIOState.pure(DispatchResult(DispatchError.cons(f'trans {blue(self.name)}: {error}'), Nil))

    def validate_transit(self, action: Transit) -> NvimIOState[D, DispatchResult]:
        def loop(tts: TransformTransState) -> NS[D, DispatchResult]:
            return tts.run(action.trans).map(L(TransComplete)(self.name, _)).flat_map(validate_trans_complete)
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

    def validate_trans_log(self, action: TransLog) -> NvimIOState[D, DispatchResult]:
        return NvimIOState.pure(DispatchResult(DispatchLog(action.message), Nil))


def validate_trans_action(name: str, action: TransAction) -> NS[D, DispatchResult]:
    val = dispatch_alg(TransValidator(name), TransAction, 'validate_')
    return val(action)


def validate_trans_complete(tc: TransComplete) -> NS[D, DispatchResult]:
    return validate_trans_action(tc.name, tc.action)


__all__ = ('validate_trans_complete',)
