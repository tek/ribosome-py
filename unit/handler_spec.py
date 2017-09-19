from typing import TypeVar, Callable

from kallikrein import Expectation, k
from kallikrein.matchers.typed import have_type
from kallikrein.matchers.maybe import be_just

from ribosome.machine.message_base import trans, message
from ribosome.machine.messages import RunIOAlg
from ribosome.machine.handler import AlgResultValidator
from ribosome.machine.trans import Transit

from amino import Right, IO, _, Either, Id, Maybe, L
from amino.state import IdState, StateT


Msg = message('Msg')
Msg2 = message('Msg2')
R = TypeVar('R')


class HandlerSpec:
    '''transition handlers
    Either[State[IO[Msg]]] $eso
    State[Either[Msg]] $se
    lift single message $single
    lift single message in state $single_st
    '''

    @property
    def validator(self) -> AlgResultValidator:
        return AlgResultValidator(1)

    def run(self, f: Callable[[Msg], R]) -> Maybe[Msg2]:
        res = self.validator.validate(f(Msg()), {})
        return k(res.resend.head).must(be_just(have_type(Msg2)))

    def eso(self) -> Expectation:
        @trans.one(Msg, trans.e, trans.st, trans.io)
        def f(msg) -> Either[str, StateT[Id, int, IO[Msg2]]]:
            return Right(IdState.pure(IO.pure(Msg2())))
        res = f(Msg())
        valid = self.validator.validate(res, {}).resend.head
        res1 = valid.to_either('').flat_map(_.io.attempt)
        valid1 = res1 / L(self.validator.validate)(_, {}) / _.resend // _.head
        return (
            k(res).must(have_type(Transit)) &
            k(res.trans).must(have_type(StateT)) &
            k(valid).must(be_just(have_type(RunIOAlg))) &
            k(valid1).must(be_just(have_type(Msg2)))
        )

    def se(self) -> Expectation:
        @trans.one(Msg, trans.st, trans.e)
        def f(msg) -> StateT[Id, int, Either[str, Msg2]]:
            return IdState.pure(Right(Msg2()))
        return self.run(f)

    def single(self) -> Expectation:
        @trans.one(Msg, trans.e)
        def f(msg) -> Either[str, Msg2]:
            return Right(Msg2())
        return self.run(f)

    def single_st(self) -> Expectation:
        @trans.one(Msg, trans.e, trans.st)
        def f(msg) -> Either[str, StateT[Id, int, Msg2]]:
            return Right(IdState.pure(Msg2()))
        return self.run(f)

__all__ = ('HandlerSpec',)
