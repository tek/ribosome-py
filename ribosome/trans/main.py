from typing import Callable, TypeVar, Type

from amino import Lists
from ribosome.trans.effect import (TransEffect, TransEffectUnit, TransEffectSingleMessage, TransEffectMessages,
                                   TransEffectResult)
from ribosome.trans.handler import FreeTransHandler, MessageTransHandler
from ribosome.dispatch.component import Component
from ribosome.trans.message_base import default_prio, Message

C = TypeVar('C', bound=Component)
D = TypeVar('D')
M = TypeVar('M', bound=Message)
R = TypeVar('R')
dp = default_prio
MDecorator = Callable[[Callable[[C], R]], MessageTransHandler[M, D]]
FDecorator = Callable[[Callable[[C], R]], FreeTransHandler[M, D]]


class MessageTransCons:

    def cons(self, msg_type: Type[M], *effects: TransEffect, prio: float=dp) -> MDecorator:
        def add_handler(func: Callable[[C], R]) -> MessageTransHandler[M, D]:
            return MessageTransHandler.create(func, msg_type, effects, prio)
        return add_handler

    def unit(self, msg_type: Type[M], *effects: TransEffect, prio: float=default_prio) -> MDecorator:
        return self.cons(msg_type, *effects, TransEffectUnit(), prio=prio)

    def one(self, tpe: Type[M], *effects: TransEffect, prio: float=dp) -> MDecorator:
        return self.cons(tpe, *effects, TransEffectSingleMessage(), prio=prio)

    def multi(self, tpe: Type[M], *effects: TransEffect, prio: float=dp) -> MDecorator:
        return self.cons(tpe, *effects, TransEffectMessages(), prio=prio)

    def relay(self, tpe: Type[M], prio: float=dp) -> Callable[[Callable[[C], R]], MessageTransHandler[M, D]]:
        def add_handler(func: Callable[[C], R]):
            return func
            # return decorate(func, tpe, prio)
        return add_handler


class FreeTransCons:

    def cons(self, *effects: TransEffect, prio: float=dp) -> FDecorator:
        def add_handler(func: Callable[[C], R]) -> FreeTransHandler[M, D]:
            return FreeTransHandler.create(func, Lists.wrap(effects), prio)
        return add_handler

    def unit(self, *effects: TransEffect, prio: float=default_prio) -> FDecorator:
        return self.cons(*effects, TransEffectUnit(), prio=prio)

    def one(self, *effects: TransEffect, prio: float=dp) -> FDecorator:
        return self.cons(*effects, TransEffectSingleMessage(), prio=prio)

    def multi(self, *effects: TransEffect, prio: float=dp) -> FDecorator:
        return self.cons(*effects, TransEffectMessages(), prio=prio)

    def result(self, *effects: TransEffect, prio: float=dp) -> FDecorator:
        return self.cons(*effects, TransEffectResult(), prio=prio)


__all__ = ('MessageTransCons', 'FreeTransCons')
