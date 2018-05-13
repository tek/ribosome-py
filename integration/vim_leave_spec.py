from kallikrein import Expectation, k

from amino.test.spec import SpecBase
from amino import do, Do, List, Map, IO, Nil, Path
from amino.test import temp_file
from amino.logging import module_log

from ribosome.test.integration.embed import TestConfig, plugin_test
from ribosome.nvim.io.compute import NvimIO
from ribosome.compute.api import prog
from ribosome.nvim.io.state import NS
from ribosome.config.basic_config import NoData
from ribosome.config.config import Config
from ribosome.rpc.api import rpc
from ribosome.nvim.api.rpc import nvim_quit
from ribosome.test.klk.expectation import await_k
from ribosome.nvim.api.variable import variable_str
from ribosome.nvim.io.api import N

log = module_log()
data = 'success'


@prog
@do(NS[NoData, None])
def vim_leave() -> Do:
    path_e = yield NS.lift(variable_str('status_file'))
    path = yield NS.e(path_e)
    yield NS.from_io(IO.delay(Path(path).write_text, data))


config: Config = Config.cons(
    name='auto',
    rpc=List(
        rpc.autocmd(vim_leave, sync=True),
    ),
    internal_component=False,
)


status_file = temp_file('vim_leave', 'status')
test_config = TestConfig.cons(config, vars=Map(status_file=str(status_file)))


@do(NvimIO[Expectation])
def quit_file() -> Do:
    text = yield N.recover_failure(N.from_io(IO.file(status_file)), lambda r: N.pure(Nil))
    return k(text) == List(data)


@do(NvimIO[Expectation])
def leave_spec() -> Do:
    yield nvim_quit()
    yield await_k(quit_file)


class AutocmdSpec(SpecBase):
    '''
    synchronously call a program at exit $leave
    '''

    def leave(self) -> Expectation:
        return plugin_test(test_config, leave_spec)


__all__ = ('AutocmdSpec',)
