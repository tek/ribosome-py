import abc
from typing import TypeVar, Type

from amino.state import StateT
from amino.tc.base import TypeClass, tc_prop, F

from ribosome.compute.prog import Prog, ProgExec, ProgBind
from ribosome.nvim.io.state import NS
from ribosome.compute.output import ProgOutputResult
from ribosome.compute.tpe import state_trans
from ribosome.compute.wrap import prog_wrappers
from ribosome.compute.tpe_data import StateProg, PlainStateProgType, RootProgType, PlainMainDataProgType


G = TypeVar('G')
D = TypeVar('D')
A = TypeVar('A')
default_prog_type = StateProg(PlainStateProgType(RootProgType(PlainMainDataProgType())))
default_prog_wrappers = prog_wrappers(default_prog_type)


def prog_lift_s(fa: NS[D, A], tpe: Type[D]) -> Prog[A]:
    return ProgBind(
        ProgExec(NS.e(state_trans(tpe)), default_prog_type, default_prog_wrappers, ProgOutputResult()),
        lambda prog_type: ProgExec(fa, prog_type, prog_wrappers(prog_type), ProgOutputResult())
    )


class TransMLift(TypeClass):

    @abc.abstractmethod
    def program_with(self, fa: F[A]) -> Prog[A]:
        ...

    @tc_prop
    def program(self, fa: F[A]) -> Prog[A]:
        return self.program_with(fa, type(fa))


class TransMLift_StateT(TransMLift, tpe=StateT):

    def program_with(self, fa: NS[D, A], tpe: Type[D]) -> Prog[A]:
        return prog_lift_s(fa, tpe)


__all__ = ('prog_lift_s',)
