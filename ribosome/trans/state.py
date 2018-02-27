import abc
from typing import TypeVar

from amino.state import StateT
from amino import Boolean, Lists
from amino.tc.base import TypeClass, tc_prop, F

from ribosome.trans.message_base import default_prio
from ribosome.trans.action import TransMCont, TransM
from ribosome.trans.effect import TransEffect
from ribosome.trans.handler import FreeTrans
from ribosome.trans.effects import TransEffectResult, TransEffectStateT


G = TypeVar('G')
D = TypeVar('D')
A = TypeVar('A')


def transm_lift_s(fa: StateT[G, D, A], *effects: TransEffect, prio: float=default_prio, **kw: Boolean) -> TransM[A]:
    eff = Lists.wrap(effects).cat(TransEffectResult()).cons(TransEffectStateT())
    return TransMCont(FreeTrans.cons(lambda: fa, eff, prio, **kw))


class TransMLift(TypeClass):

    @abc.abstractmethod
    def trans_with(self, fa: F[A], *effects: TransEffect, prio: float=default_prio, **kw: Boolean) -> TransM[A]:
        ...

    @tc_prop
    def trans(self, fa: F[A]) -> TransM[A]:
        return self.trans_with(fa)


class TransMLift_StateT(TransMLift, tpe=StateT):

    def trans_with(self, fa: F[A], *effects: TransEffect, prio: float=default_prio, **kw: Boolean) -> TransM[A]:
        return transm_lift_s(fa, *effects, prio=prio, **kw)


__all__ = ('transm_lift_s',)
