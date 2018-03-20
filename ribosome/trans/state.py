import abc
from typing import TypeVar

from amino.state import StateT
from amino import Boolean, Lists
from amino.tc.base import TypeClass, tc_prop, F

from ribosome.trans.handler import Trans
from ribosome.trans.effect import TransEffect
from ribosome.trans.handler import TransF
from ribosome.trans.effects import TransEffectResult, TransEffectStateT


G = TypeVar('G')
D = TypeVar('D')
A = TypeVar('A')


def transm_lift_s(fa: StateT[G, D, A], *effects: TransEffect, **kw: Boolean) -> Trans[A]:
    eff = Lists.wrap(effects).cat(TransEffectResult()).cons(TransEffectStateT())
    return TransF.cons(lambda: fa, eff, **kw)


class TransMLift(TypeClass):

    @abc.abstractmethod
    def trans_with(self, fa: F[A], *effects: TransEffect, **kw: Boolean) -> Trans[A]:
        ...

    @tc_prop
    def trans(self, fa: F[A]) -> Trans[A]:
        return self.trans_with(fa)


class TransMLift_StateT(TransMLift, tpe=StateT):

    def trans_with(self, fa: F[A], *effects: TransEffect, **kw: Boolean) -> Trans[A]:
        return transm_lift_s(fa, *effects, **kw)


__all__ = ('transm_lift_s',)
