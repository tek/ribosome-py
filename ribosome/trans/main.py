from typing import Callable, TypeVar

from amino import Lists, Boolean
from ribosome.trans.effect import TransEffect
from ribosome.trans.effects import TransEffectUnit, TransEffectResult
from ribosome.trans.handler import TransF
from ribosome.dispatch.component import Component
from ribosome.trans.recursive_effects import TransEffectDo

C = TypeVar('C', bound=Component)
A = TypeVar('A')
R = TypeVar('R')
TransDecorator = Callable[[Callable[[C], R]], TransF[A]]


class TransCons:

    def cons(self, *effects: TransEffect, **kw: Boolean) -> TransDecorator:
        def add_handler(func: Callable[[C], R]) -> TransF[A]:
            return TransF.cons(func, Lists.wrap(effects), **kw)
        return add_handler

    def unit(self, *effects: TransEffect, **kw: Boolean) -> TransDecorator:
        return self.cons(*effects, TransEffectUnit(), **kw)

    def result(self, *effects: TransEffect, **kw: Boolean) -> TransDecorator:
        return self.cons(*effects, TransEffectResult(), **kw)

    def do(self, **kw: Boolean) -> TransDecorator:
        return self.cons(TransEffectDo(), **kw)


__all__ = ('TransCons',)
