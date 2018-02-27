from typing import Callable, TypeVar, Type

from amino import Lists, Boolean
from ribosome.trans.effect import TransEffect
from ribosome.trans.effects import (TransEffectUnit, TransEffectSingleMessage, TransEffectMessages, TransEffectResult,
                                    TransEffectDo)
from ribosome.trans.handler import FreeTrans, MessageTrans
from ribosome.dispatch.component import Component
from ribosome.trans.message_base import default_prio, Message

C = TypeVar('C', bound=Component)
A = TypeVar('A')
M = TypeVar('M', bound=Message)
R = TypeVar('R')
dp = default_prio
MDecorator = Callable[[Callable[[C], R]], MessageTrans[M, A]]
FDecorator = Callable[[Callable[[C], R]], FreeTrans[A]]


class MessageTransCons:

    def cons(self, msg_type: Type[M], *effects: TransEffect, prio: float=dp) -> MDecorator:
        def add_handler(func: Callable[[C], R]) -> MessageTrans[M, A]:
            return MessageTrans.create(func, msg_type, effects, prio)
        return add_handler

    def unit(self, msg_type: Type[M], *effects: TransEffect, prio: float=default_prio) -> MDecorator:
        return self.cons(msg_type, *effects, TransEffectUnit(), prio=prio)

    def one(self, tpe: Type[M], *effects: TransEffect, prio: float=dp) -> MDecorator:
        return self.cons(tpe, *effects, TransEffectSingleMessage(), prio=prio)

    def multi(self, tpe: Type[M], *effects: TransEffect, prio: float=dp) -> MDecorator:
        return self.cons(tpe, *effects, TransEffectMessages(), prio=prio)

    def relay(self, tpe: Type[M], prio: float=dp) -> Callable[[Callable[[C], R]], MessageTrans[M, A]]:
        def add_handler(func: Callable[[C], R]):
            return func
            # return decorate(func, tpe, prio)
        return add_handler


class FreeTransCons:

    def cons(self, *effects: TransEffect, prio: float=dp, **kw: Boolean) -> FDecorator:
        def add_handler(func: Callable[[C], R]) -> FreeTrans[A]:
            return FreeTrans.cons(func, Lists.wrap(effects), prio, **kw)
        return add_handler

    def unit(self, *effects: TransEffect, prio: float=default_prio, **kw: Boolean) -> FDecorator:
        return self.cons(*effects, TransEffectUnit(), prio=prio, **kw)

    def one(self, *effects: TransEffect, prio: float=dp, **kw: Boolean) -> FDecorator:
        return self.cons(*effects, TransEffectSingleMessage(), prio=prio, **kw)

    def multi(self, *effects: TransEffect, prio: float=dp, **kw: Boolean) -> FDecorator:
        return self.cons(*effects, TransEffectMessages(), prio=prio, **kw)

    def result(self, *effects: TransEffect, prio: float=dp, **kw: Boolean) -> FDecorator:
        return self.cons(*effects, TransEffectResult(), prio=prio, **kw)

    def do(self, prio: float=dp, **kw: Boolean) -> FDecorator:
        return self.cons(TransEffectDo(), prio=prio, **kw)


__all__ = ('MessageTransCons', 'FreeTransCons')
