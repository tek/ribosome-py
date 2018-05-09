from kallikrein import Expectation, k
from kallikrein.matchers.either import be_right
from kallikrein.matchers import contain

from chiasma.test.tmux_spec import tmux_spec_socket
from chiasma.util.pid import discover_pane_by_pid, child_pids

from amino.test.spec import SpecBase
from amino import do, Do, List, Map

from ribosome.test.integration.tmux import tmux_plugin_test
from ribosome.nvim.io.compute import NvimIO
from ribosome.config.config import Config
from ribosome.rpc.api import rpc
from ribosome.nvim.api.rpc import nvim_pid
from ribosome.nvim.io.state import NS
from ribosome.compute.api import prog
from ribosome.test.config import TestConfig
from ribosome.nvim.api.function import nvim_call_tpe
from ribosome.util.tmux import tmux_to_nvim


@prog
def vim_pid() -> NS[None, int]:
    return NS.lift(nvim_pid())


config: Config[None, None] = Config.cons(
    'tmux',
    rpc=List(rpc.write(vim_pid))
)
vars = Map(
    tmux_tmux_socket=tmux_spec_socket,
)
test_config = TestConfig.cons(config, vars=vars)


@do(NvimIO[Expectation])
def vim_pid_spec() -> Do:
    pid = yield nvim_call_tpe(int, 'TmuxVimPid')
    pane = yield tmux_to_nvim(discover_pane_by_pid(pid))
    return k(child_pids(pane.pid).attempt).must(be_right(contain(pid)))


class TmuxSpec(SpecBase):
    '''
    find the vim pid $find_vim_pid
    '''

    def find_vim_pid(self) -> Expectation:
        return tmux_plugin_test(test_config, vim_pid_spec)


__all__ = ('TmuxSpec',)
