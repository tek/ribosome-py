from typing import Callable, Any

from kallikrein import Expectation, k
from kallikrein.matchers.either import be_right
from kallikrein.matchers.match_with import match_with

from amino import do, IO, Do, List, Just, Nil, _

from ribosome.test.klk.matchers.nresult import nsuccess
from ribosome.nvim.io.compute import NvimIO
from ribosome.test.integration.embed import setup_test_nvim, TestConfig
from ribosome.nvim.api.rpc import nvim_quit
from ribosome.nvim.io.api import N
from ribosome.nvim.io.data import NResult
from ribosome.rpc.state import cons_state
from ribosome.data.plugin_state import PS
from ribosome.nvim.io.state import NS
from ribosome.logging import nvim_logging
from ribosome.components.internal.update import init_rpc
from ribosome.rpc.api import RpcProgram
from ribosome.rpc.comm import Comm
from ribosome.rpc.to_plugin import run_program
from ribosome.rpc.data.rpc import RpcArgs


def program_runner(args: List[Any]) -> Callable[[RpcProgram], NS[PS, Any]]:
    def runner(program: RpcProgram) -> NS[PS, Any]:
        return run_program(program, RpcArgs.cons(args))
    return runner


@do(NS[PS, Any])
def request(method: str, args: List[Any]) -> Do:
    progs = yield NS.inspect(_.programs)
    matches = progs.filter(lambda a: a.program.name == method)
    yield matches.traverse(program_runner(args), NS)


@do(NvimIO[PS])
def init_state(config: TestConfig, components: List[str]=Nil) -> Do:
    log_handler = yield N.delay(nvim_logging)
    state = cons_state(config.config, config.io_interpreter, config.logger, log_handler=log_handler)
    yield init_rpc(Just(config.components)).run_s(state)


@do(NvimIO[PS])
def setup_engine(config: TestConfig) -> Do:
    yield init_state(config)


def cleanup(comm: Comm) -> Do:
    '''for some reason, the loop gets stuck if `quit` is called only once.
    '''
    @do(NvimIO[None])
    def cleanup(result: NResult) -> Do:
        yield nvim_quit()
        yield nvim_quit()
    return cleanup


@do(NvimIO[Expectation])
def run_test(
        config: TestConfig,
        io: Callable[[], NS[PS, Expectation]],
) -> Do:
    yield config.pre()
    engine = yield setup_engine(config)
    yield io().run_a(engine)


def external_state_test(config: TestConfig, io: Callable[[], NS[PS, Expectation]]) -> Expectation:
    @do(IO[Expectation])
    def run() -> Do:
        nvim = yield setup_test_nvim(config)
        return N.ensure(run_test(config, io), cleanup(nvim.comm)).run_a(nvim.api)
    return k(run().attempt).must(be_right(nsuccess(match_with(lambda a: a))))


def external_test(config: TestConfig, io: Callable[[], NvimIO[Expectation]]) -> Expectation:
    return external_state_test(config, lambda: NS.lift(io()))


__all__ = ('external_test',)
