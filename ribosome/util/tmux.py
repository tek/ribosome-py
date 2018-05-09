from typing import TypeVar

from amino.tc.base import tc_prop
from amino import do, Do

from chiasma.io.compute import TmuxIO
from chiasma.tmux import Tmux
from chiasma.io.state import TmuxIOState

from ribosome.nvim.io.state import ToNvimIOState, NS
from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.variable import variable_prefixed_str
from ribosome.nvim.io.api import N

A = TypeVar('A')
S = TypeVar('S')


@do(NvimIO[Tmux])
def tmux_from_vim() -> Do:
    socket = yield variable_prefixed_str('tmux_socket')
    return Tmux.cons(socket=socket | None)


@do(NvimIO[A])
def tmux_to_nvim(tm: TmuxIO[A]) -> Do:
    tmux = yield tmux_from_vim()
    yield N.from_either(tm.either(tmux))


class TmuxStateToNvimIOState(ToNvimIOState, tpe=TmuxIOState):

    @tc_prop
    def nvim(self, fa: TmuxIOState[S, A]) -> NS:
        return fa.transform_f(NS, tmux_to_nvim)


__all__ = ('TmuxStateToNvimIOState',)
