import abc
from typing import Callable, TypeVar, Type, Generic, Any

from amino import List, Lists
from amino.dat import Dat

from ribosome.trans.effect import TransEffect, cont, lift
from ribosome.trans.action import TransAction, TransM, TransMPure
from ribosome.trans.message_base import Message
from ribosome.dispatch.component import Component

D = TypeVar('D')
M = TypeVar('M', bound=Message)
R = TypeVar('R')
O = TypeVar('O')
A = TypeVar('A')
B = TypeVar('B')


class TransComplete(Dat['TransComplete']):

    def __init__(self, name: str, action: TransAction) -> None:
        self.name = name
        self.action = action


def extract(name: str, output: O, effects: List[TransEffect]) -> TransComplete:
    trans_result = cont(effects, False, lambda f: f(output)) | output
    return TransComplete(name, lift(trans_result, False))


class TransHandler(abc.ABC):

    @abc.abstractmethod
    def __call__(self, *args: Any) -> 'TransHandler':
        ...


class MessageTransHandler(Generic[M, D], Dat['MessageTransHandler[M, D]'], TransHandler):

    @staticmethod
    def create(fun: Callable[[M], R], msg: Type[M], effects: List[TransEffect], prio: float) -> 'TransHandler':
        name = fun.__name__
        return MessageTransHandler(name, fun, msg, effects, prio)

    def __init__(self, name: str, fun: Callable[[M], R], message: Type[M], effects: List[TransEffect], prio: float
                 ) -> None:
        self.name = name
        self.message = message
        self.fun = fun
        self.prio = prio
        self.effects = effects

    def run(self, component: Component, msg: M) -> TransAction:
        return extract(self.name, self.fun(component, msg), Lists.wrap(self.effects))

    def __call__(self, *args: Any) -> 'MessageTransHandler':
        return self


class FreeTransHandler(Generic[D, R], Dat['FreeTransHandler[M, D]'], TransHandler):

    @staticmethod
    def create(fun: Callable[..., R], effects: List[TransEffect], prio: float) -> 'TransHandler':
        name = fun.__name__
        return FreeTransHandler(name, fun, (), effects, prio)

    def __init__(self, name: str, fun: Callable[..., R], args: tuple, effects: List[TransEffect], prio: float) -> None:
        self.name = name
        self.fun = fun
        self.args = args
        self.effects = effects
        self.prio = prio

    def __call__(self, *args: Any) -> 'FreeTransHandler':
        return self.copy(args=args)

    def run(self) -> TransAction:
        return extract(self.name, self.fun(*self.args), Lists.wrap(self.effects))

    @property
    def m(self) -> TransM:
        return TransMPure(self)


__all__ = ('MessageTransHandler', 'FreeTransHandler')
