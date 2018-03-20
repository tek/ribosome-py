from ribosome.trans.effects import (TransEffect, TransEffectStateT, TransEffectIO, TransEffectNvimIO, TransEffectResult,
                                    TransEffectLog)
from ribosome.trans.main import TransCons
from ribosome.trans.recursive_effects import TransEffectDo, TransEffectGatherIOs, TransEffectGatherSubprocs


class TransApi:
    st: TransEffect = TransEffectStateT()
    io: TransEffect = TransEffectIO()
    gather_ios: TransEffect = TransEffectGatherIOs()
    gather_subprocs: TransEffect = TransEffectGatherSubprocs()
    nio: TransEffect = TransEffectNvimIO()
    result: TransEffect = TransEffectResult()
    do: TransEffect = TransEffectDo()
    log: TransEffect = TransEffectLog()
    free: TransCons = TransCons()


trans = TransApi()


__all__ = ('TransApi', 'trans')
