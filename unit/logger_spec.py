from kallikrein import Expectation, k
from kallikrein.matchers import contain

from amino import Dat, List, Nil, __, do, Do
from amino.test.spec import SpecBase

from ribosome.config.config import Config
from ribosome.compute.output import Echo
from ribosome.nvim.io.state import NS
from ribosome.compute.api import prog
from ribosome.rpc.api import rpc
from ribosome.test.config import TestConfig
from ribosome.test.prog import request
from ribosome.test.unit import unit_test


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
test_config = TestConfig.cons(config, logger=logger)


@do(NS[LSData, Expectation])
def logger_spec() -> Do:
    yield request('log_something')
    log = yield NS.inspect(lambda s: s.data.log)
    return k(log).must(contain(test_echo))


class LoggerSpec(SpecBase):
    '''
    use a custom logger $logger
    '''

    def logger(self) -> Expectation:
        return unit_test(test_config, logger_spec)


__all__ = ('LoggerSpec',)
