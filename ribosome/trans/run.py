import abc
from typing import Callable, TypeVar

from ribosome.trans.effect import TransEffect
from ribosome.trans.step import TransStep, Lift, Strict, TransEffectError
from ribosome.trans.action import TransAction, Transit, TransFailure, TransM, TransMCont
from ribosome.trans.message_base import Message
from ribosome.request.args import ArgValidator
from ribosome.trans.handler import MessageTrans, FreeTrans, TransHandler

from amino.dispatch import PatMat
from amino import Dat, List, Maybe, L, _, Lists, Either
from amino.string.hues import red
from amino.tc.base import TypeClass, tc_prop

A = TypeVar('A')
M = TypeVar('M', bound=Message)
R = TypeVar('R')
O = TypeVar('O')


def cont(tail: List[TransEffect], in_state: bool, f: Callable[[Callable[[R], TransStep]], TransStep]
         ) -> Maybe[TransStep]:
    return tail.detach_head.map2(lambda h, t: f(lambda a: h.run(a, t, in_state)))


class lift(PatMat, alg=TransStep):

    def lift(self, res: Lift, in_state: bool) -> TransAction:
        return self(res.data, in_state)

    def strict(self, res: Strict, in_state: bool) -> TransAction:
        return Transit(res.data / L(self)(_, True))

    def trans_effect_error(self, res: TransEffectError, in_state: bool) -> TransAction:
        return TransFailure(res.data)

    def patmat_default(self, res: R, in_state: bool) -> TransAction:
        return (
            res
            if isinstance(res, TransAction) else
            TransFailure(f'transition did not produce `TransAction`: {red(res)}')
        )


class TransComplete(Dat['TransComplete']):

    def __init__(self, name: str, action: TransAction) -> None:
        self.name = name
        self.action = action


def extract(name: str, output: O, effects: List[TransEffect]) -> TransComplete:
    trans_result = cont(effects, False, lambda f: f(output)) | output
    return TransComplete(name, lift.match(trans_result, False))


def run_message_trans_handler(handler: MessageTrans[A, M], msg: M) -> TransComplete:
    return extract(handler.name, handler.fun(msg), Lists.wrap(handler.effects))


def execute_free_trans_handler(handler: FreeTrans[A]) -> Either[TransAction, O]:
    val = ArgValidator(handler.params_spec)
    return val.either(handler.args, 'trans', handler.name).bimap(TransFailure, lambda a: handler.fun(*handler.args))


def run_free_trans_handler(handler: FreeTrans[A]) -> TransComplete:
    return (
        execute_free_trans_handler(handler)
        .cata(
            L(TransComplete)(handler.name, _),
            L(extract)(handler.name, _, Lists.wrap(handler.effects)),
        )
    )


class TransHandlerOps(TypeClass):

    @abc.abstractmethod
    def m(self, handler: TransHandler[A]) -> TransM:
        ...


class FreeTransHandlerOps(TransHandlerOps, tpe=FreeTrans):

    @tc_prop
    def m(self, handler: FreeTrans[A]) -> TransM:
        return TransMCont(handler)


__all__ = ('cont', 'lift', 'TransComplete', 'extract')
