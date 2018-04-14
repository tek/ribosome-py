from typing import GenericMeta, TypeVar, Callable, Type

from amino.lenses.lens import lens
from amino import do, Do, _

from ribosome.nvim.io.state import NS
from ribosome.config.settings import Settings
from ribosome.compute.ribosome import Ribosome
from ribosome.config.setting import Setting
from ribosome.nvim.io.compute import NvimIO
from ribosome.compute.api import prog
from ribosome.compute.prog import Prog, ProgExec
from ribosome.compute.output import ProgOutputResult
from ribosome.compute.tpe_data import StateProg, trivial_state_prog, ribo_state_prog
from ribosome.compute.wrap import prog_wrappers
from ribosome.data.plugin_state import PluginState

A = TypeVar('A')
S = TypeVar('S', bound=Settings)
D = TypeVar('D')
M = TypeVar('M')
CC = TypeVar('CC')
C = TypeVar('C')
R = TypeVar('R')
main_lens = lens.state.data


class RMeta(GenericMeta):
    pass


class Ribo(metaclass=RMeta):

    @classmethod
    def setting(self, attr: Callable[[S], Setting[A]]) -> NS[Ribosome[S, D, CC, C], A]:
        def get(rib: Ribosome[S, D, CC, C]) -> NvimIO[A]:
            return attr(rib.state.basic.settings).value_or_default
        return NS.inspect_f(get)

    @classmethod
    @prog
    def setting_prog(self, attr: Callable[[S], Setting[A]]) -> NS[Ribosome[S, D, CC, C], A]:
        def get(rib: Ribosome[S, D, CC, C]) -> NvimIO[A]:
            return attr(rib.state.basic.settings).value_or_default
        return NS.inspect_f(get)

    @classmethod
    def settings(self) -> NS[Ribosome[S, D, CC, C], S]:
        return NS.inspect(lambda a: a.ps.settings)

    @classmethod
    def comp(self) -> NS[Ribosome[S, D, CC, C], C]:
        return NS.inspect(lambda a: a.comp_lens.get()(a))

    @classmethod
    def inspect_comp(self, f: Callable[[C], A]) -> NS[Ribosome[S, D, CC, C], A]:
        return NS.inspect(lambda a: f(a.comp_lens.get()(a)))

    @classmethod
    def inspect_comp_e(self, f: Callable[[C], A]) -> NS[Ribosome[S, D, CC, C], A]:
        return NS.inspect_either(lambda a: f(a.comp_lens.get()(a)))

    @classmethod
    def modify_comp(self, f: Callable[[C], C]) -> NS[Ribosome[S, D, CC, C], None]:
        return NS.modify(lambda a: a.comp_lens.modify(f)(a))

    @classmethod
    def main(self) -> NS[Ribosome[S, D, CC, C], C]:
        return NS.inspect(lambda a: main_lens.get()(a))

    @classmethod
    def modify_main(self, f: Callable[[D], D]) -> NS[Ribosome[S, D, CC, C], None]:
        return NS.modify(lambda a: main_lens.modify(f)(a))

    @classmethod
    @do(NS[Ribosome[S, D, CC, C], A])
    def zoom_comp(self, fa: NS[C, A]) -> Do:
        lens = yield NS.inspect(_.comp_lens)
        yield fa.zoom(lens)

    @classmethod
    @do(Prog[A])
    def lift_state_prog(self, fa: NS[Ribosome[S, D, CC, C], A], state_type: StateProg[M, C, R]) -> Do:
        wrappers = yield Prog.from_either(prog_wrappers.match(state_type))
        yield ProgExec(fa, wrappers, ProgOutputResult())

    @classmethod
    @do(Prog[A])
    def lift(self, fa: NS[Ribosome[S, D, CC, C], A], comp: Type[C]) -> Do:
        state_type: StateProg[PluginState[S, D, CC], C, Ribosome[S, D, CC, C]] = ribo_state_prog(comp)
        yield Ribo.lift_state_prog(fa, state_type)

    @classmethod
    def lift_comp(self, fa: NS[C, A], comp: Type[C]) -> Prog[A]:
        return Ribo.lift(Ribo.zoom_comp(fa), comp)

    @classmethod
    def trivial(self, fa: NS[D, A]) -> Prog[A]:
        return Ribo.lift_state_prog(fa, trivial_state_prog)

    @classmethod
    def lift_nvimio(self, fa: NvimIO[A]) -> Prog[A]:
        return Ribo.trivial(NS.lift(fa))


__all__ = ('Ribosome', 'Ribo')
