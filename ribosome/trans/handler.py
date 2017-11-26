from typing import Callable, TypeVar, Type, Generic

from amino import List, Lists
from amino.dat import Dat

from ribosome.trans.effect import TransEffect, cont, lift
from ribosome.trans.action import TransAction
from ribosome.trans.message_base import Message
from ribosome.trans.legacy import Handler

D = TypeVar('D')
M = TypeVar('M', bound=Message)
R = TypeVar('R')
O = TypeVar('O')


def extract(output: O, effects: List[TransEffect]) -> TransAction:
    trans_result = cont(effects, False, lambda f: f(output)) | output
    return lift(trans_result, False)


class MessageTransHandler(Generic[M, D], Dat['MessageTransHandler[M, D]'], Handler):

    @staticmethod
    def create(fun: Callable[[M], R], msg: Type[M], effects: List[TransEffect], prio: float) -> 'Handler[M, D, R]':
        name = fun.__name__
        return MessageTransHandler(name, fun, msg, prio, effects)

    def __init__(self, name: str, fun: Callable[[M], R], message: Type[M], prio: float,
                 effects: List[TransEffect]) -> None:
        self.name = name
        self.message = message
        self.fun = fun
        self.prio = prio
        self.effects = effects

    def run(self, msg: M) -> TransAction:
        return extract(self.fun(msg), Lists.wrap(self.effects))


class FreeTransHandler(Generic[D, R], Dat['FreeTransHandler[M, D]'], Handler):

    @staticmethod
    def create(fun: Callable[..., R], effects: List[TransEffect], prio: float) -> 'Handler[D, R]':
        name = fun.__name__
        return FreeTransHandler(name, fun, prio, effects)

    def __init__(self, name: str, fun: Callable[..., R], prio: float, effects: List[TransEffect]) -> None:
        self.name = name
        self.fun = fun
        self.prio = prio
        self.effects = effects

    def run(self, args: tuple) -> TransAction:
        return extract(self.fun(*args), Lists.wrap(self.effects))


__all__ = ('MessageTransHandler', 'FreeTransHandler')
