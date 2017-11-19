from typing import Callable, TypeVar, Type, Generic

from ribosome.machine.message_base import Message

from amino import List, Lists
from ribosome.data import Data
from ribosome.machine.machine import Machine
from ribosome.trans.effect import TransEffect, cont, lift
from ribosome.trans.action import TransAction

D = TypeVar('D', bound=Data)
M = TypeVar('M', bound=Message)
R = TypeVar('R')
O = TypeVar('O')


def extract(output: O, effects: List[TransEffect]) -> TransAction:
    trans_result = cont(effects, False, lambda f: f(output)) | output
    return lift(trans_result, False)


class MessageTransHandler(Generic[M, D]):

    @staticmethod
    def create(fun: Callable[..., R], msg: Type[M], effects: List[TransEffect], prio: float) -> 'Handler[M, D, R]':
        name = fun.__name__
        return MessageTransHandler(name, fun, msg, prio, effects)

    def __init__(self, name: str, fun: Callable[[Machine, M], R], message: Type[M], prio: float,
                 effects: List[TransEffect]) -> None:
        self.name = name
        self.message = message
        self.fun = fun
        self.prio = prio
        self.effects = effects

    def execute(self, machine: Machine, msg: M) -> TransAction:
        return extract(self.fun(machine, msg), Lists.wrap(self.effects))

    # def execute(self, machine: Machine, msg: M) -> TransAction:
    #     trans = self.trans_tpe(machine, msg)
    #     return self.handler.fun(trans)


class FreeTransHandler(Generic[M, D]):

    @staticmethod
    def create(fun: Callable[..., R], effects: List[TransEffect], prio: float) -> 'Handler[M, D, R]':
        name = fun.__name__
        return FreeTransHandler(name, fun, prio, effects)

    def __init__(self, name: str, fun: Callable[[D, M], R], prio: float, effects: List[TransEffect]) -> None:
        self.name = name
        self.fun = fun
        self.prio = prio
        self.effects = effects

    def run(self, args: tuple) -> TransAction:
        return extract(self.fun(*args), Lists.wrap(self.effects))


__all__ = ('MessageTransHandler', 'FreeTransHandler')
