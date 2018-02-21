from typing import TypeVar

from kallikrein import Expectation, k
from kallikrein.matchers.typed import have_type
from kallikrein.matchers.maybe import be_just
from kallikrein.matchers.either import be_right

from ribosome.trans.api import trans
from ribosome.trans.message_base import pmessage
from ribosome.trans.action import Transit, Propagate
from ribosome.dispatch.transform import TransValidator, validate_trans_complete
from ribosome.dispatch.data import DispatchResult, DispatchIO
from ribosome.trans.handler import MessageTransHandler
from ribosome.trans.run import TransComplete, run_message_trans_handler

from amino import Right, IO, _, Either, Id, Maybe
from amino.state import IdState, StateT


Msg1 = pmessage('Msg1')
Msg2 = pmessage('Msg2')
R = TypeVar('R')


class HandlerSpec:
    '''transition handlers
    Either[State[IO[Msg1]]] $eso
    State[Either[Msg1]] $se
    lift single message $single
    lift single message in state $single_st
    '''

    def validate(self, action: TransComplete) -> TransValidator:
        return validate_trans_complete(action)

    def run(self, f: MessageTransHandler) -> Maybe[Msg2]:
        res = self.validate(run_message_trans_handler(f, Msg1()))
        return k(res.run_a(None).attempt(None) / _.msgs // _.head).must(be_just(have_type(Msg2)))

    def eso(self) -> Expectation:
        @trans.msg.one(Msg1, trans.e, trans.st, trans.io)
        def f(msg: Msg1) -> Either[str, StateT[Id, int, IO[Msg2]]]:
            return Right(IdState.pure(IO.pure(Msg2())))
        res = run_message_trans_handler(f, Msg1())
        s = self.validate(res)
        valid = s.run_a(None).attempt(None)
        action = res.action
        return (
            k(action).must(have_type(Transit)) &
            k(action.trans).must(have_type(StateT)) &
            k(valid).must(be_right(have_type(DispatchResult))) &
            k(valid / _.output).must(be_right(have_type(DispatchIO))) &
            k(valid / _.output.io.io // _.attempt).must(be_right(Propagate.one(Msg2())))
        )

    def se(self) -> Expectation:
        @trans.msg.one(Msg1, trans.st, trans.e)
        def f(msg: Msg1) -> StateT[Id, int, Either[str, Msg2]]:
            return IdState.pure(Right(Msg2()))
        return self.run(f)

    def single(self) -> Expectation:
        @trans.msg.one(Msg1, trans.e)
        def f(msg: Msg1) -> Either[str, Msg2]:
            return Right(Msg2())
        return self.run(f)

    def single_st(self) -> Expectation:
        @trans.msg.one(Msg1, trans.e, trans.st)
        def f(msg: Msg1) -> Either[str, StateT[Id, int, Msg2]]:
            return Right(IdState.pure(Msg2()))
        return self.run(f)

__all__ = ('HandlerSpec',)
