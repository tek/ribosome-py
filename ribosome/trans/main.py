from typing import Callable, TypeVar

from amino import Lists, Boolean
from ribosome.trans.effect import TransEffect
from ribosome.trans.effects import TransEffectUnit, TransEffectResult
from ribosome.compute.prog import ProgF
from ribosome.trans.recursive_effects import TransEffectDo
from ribosome.config.settings import Settings
from ribosome.request.args import ParamsSpec
from ribosome.compute.tpe import analyze_trans_tpe
from ribosome.compute.wrap import trans_wrappers
from ribosome.compute.prog import Program

A = TypeVar('A')
S = TypeVar('S', bound=Settings)
TransDecorator = Callable[[Callable[..., A]], ProgF[A]]


def analyze_trans(func: Callable[..., A], *effects: TransEffect, **kw: Boolean) -> Program[A]:
    params = ParamsSpec.from_function(func)
    tpe = analyze_trans_tpe(params).get_or_raise()
    wrappers = trans_wrappers(tpe)
    return Program(ProgF.cons(func, params, Lists.wrap(effects), **kw), tpe, wrappers)


class TransCons:

    def cons(self, *effects: TransEffect, **kw: Boolean) -> TransDecorator:
        def add_handler(func: Callable[..., A]) -> ProgF[A]:
            return analyze_trans(func, *effects, **kw)
        return add_handler

    def unit(self, *effects: TransEffect, **kw: Boolean) -> TransDecorator:
        return self.cons(*effects, TransEffectUnit(), **kw)

    def result(self, *effects: TransEffect, **kw: Boolean) -> TransDecorator:
        return self.cons(*effects, TransEffectResult(), **kw)

    def do(self, **kw: Boolean) -> TransDecorator:
        return self.cons(TransEffectDo(), **kw)


__all__ = ('TransCons',)
