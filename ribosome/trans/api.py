from ribosome.trans.effects import (TransEffect, TransEffectMaybe, TransEffectEither, TransEffectStateT, TransEffectIO,
                                    TransEffectNvimIO, TransEffectCoro, TransEffectSingleMessage, TransEffectMessages,
                                    TransEffectUnit, TransEffectResult, TransEffectGatherIOs, TransEffectDo,
                                    TransEffectGatherSubprocs, TransEffectLog)
from ribosome.trans.main import FreeTransCons, MessageTransCons


class TransApi:
    m: TransEffect = TransEffectMaybe()
    e: TransEffect = TransEffectEither()
    st: TransEffect = TransEffectStateT()
    io: TransEffect = TransEffectIO()
    gather_ios: TransEffect = TransEffectGatherIOs()
    gather_subprocs: TransEffect = TransEffectGatherSubprocs()
    nio: TransEffect = TransEffectNvimIO()
    coro: TransEffect = TransEffectCoro()
    single: TransEffect = TransEffectSingleMessage()
    strict: TransEffect = TransEffectMessages()
    none: TransEffect = TransEffectUnit()
    result: TransEffect = TransEffectResult()
    do: TransEffect = TransEffectDo()
    log: TransEffect = TransEffectLog()
    free: FreeTransCons = FreeTransCons()
    msg: MessageTransCons = MessageTransCons()


trans = TransApi()


__all__ = ('TransApi', 'trans')
