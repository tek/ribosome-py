from ribosome.trans.effect import (TransEffect, TransEffectMaybe, TransEffectEither, TransEffectStateT, TransEffectIO,
                                   TransEffectNvimIO, TransEffectCoro, TransEffectSingleMessage, TransEffectMessages,
                                   TransEffectUnit, TransEffectResult)
from ribosome.trans.main import FreeTransCons, MessageTransCons


class TransApi:
    m: TransEffect = TransEffectMaybe()
    e: TransEffect = TransEffectEither()
    st: TransEffect = TransEffectStateT()
    io: TransEffect = TransEffectIO()
    nio: TransEffect = TransEffectNvimIO()
    coro: TransEffect = TransEffectCoro()
    single: TransEffect = TransEffectSingleMessage()
    strict: TransEffect = TransEffectMessages()
    none: TransEffect = TransEffectUnit()
    result: TransEffect = TransEffectResult()
    free: FreeTransCons = FreeTransCons()
    msg: MessageTransCons = MessageTransCons()


trans = TransApi()

__all__ = ('TransApi', 'trans')
