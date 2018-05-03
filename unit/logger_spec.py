from kallikrein import Expectation, k
from kallikrein.matchers.match_with import match_with
from kallikrein.matchers import contain

from amino import Dat, List, Nil, __
from amino.test.spec import SpecBase

from ribosome.config.config import Config
from ribosome.request.handler.handler import rpc
from ribosome.compute.output import Echo
from ribosome.nvim.io.state import NS
from ribosome.compute.api import prog
from ribosome.test.integration.run import RequestHelper
from ribosome.data.plugin_state import PluginState
from ribosome.config.component import NoComponentData


class LSData(Dat['LSData']):

    def __init__(self, log: List[Echo]=Nil) -> None:
        self.log = log


test_echo = Echo.info('text')


@prog.echo
def log_something() -> NS[LSData, None]:
    return NS.pure(test_echo)


@prog
def logger(msg: Echo) -> NS[LSData, None]:
    return NS.modify(__.append1.log(msg))


config: Config = Config.cons(
    'logger',
    state_ctor=LSData,
    rpc=List(
        rpc.write(log_something),
    ),
)
helper = RequestHelper.cons(config, logger=logger).strict()


class LoggerSpec(SpecBase):
    '''
    use a custom logger $logger
    '''

    def logger(self) -> Expectation:
        def check(state: PluginState[LSData, NoComponentData]) -> Expectation:
            return k(state.data.log).must(contain(test_echo))
        return helper.k(helper.run_s, 'log_something').must(contain(match_with(check)))


__all__ = ('LoggerSpec',)
