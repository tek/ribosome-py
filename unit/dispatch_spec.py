from typing import Any

from kallikrein import Expectation, k, pending

from amino.test.spec import SpecBase
from amino import Lists, List, _, IO, __, do, Do
from amino.boolean import true
from amino.dat import Dat, ADT

from ribosome.compute.api import prog
from ribosome.plugin_state import PluginState, DispatchConfig
from ribosome.request.handler.handler import RequestHandler
from ribosome.nvim.io.state import NS
from ribosome.test.integration.run import DispatchHelper
from ribosome.config.config import Config
from ribosome.dispatch.execute import execute_request
from ribosome.config.settings import Settings
from ribosome.nvim.io.api import N

specimen = Lists.random_string()


class HsData(Dat['HsData']):

    def __init__(self, counter: int=7) -> None:
        self.counter = counter


@prog.result
def trans_free(a: int, b: str='b') -> NS[None, int]:
    return NS.pure(8)


@prog.result
def trans_io() -> IO[int]:
    return IO.pure(5)


# TODO allow args here
@prog.result
def trans_internal() -> NS[PluginState, str]:
    return NS.inspect(_.name)


@prog.unit
def trans_data() -> NS[HsData, None]:
    return NS.modify(__.set.counter(23))


class JData(ADT['JData']):

    def __init__(self, number: int, name: str, items: List[str]) -> None:
        self.number = number
        self.name = name
        self.items = items


@prog.result
def trans_json(a: int, b: str, data: JData) -> NS[HsData, int]:
    return NS.pure(data.number + a)


@prog.unit
@do(NS[HsData, None])
def vim_enter() -> Do:
    yield NS.modify(__.copy(counter=19))


@prog.result
def trans_error() -> NS[HsData, int]:
    return NS.lift(N.error('error'))


config: Config[Settings, HsData, Any] = Config.cons(
    'hs',
    request_handlers=List(
        RequestHandler.trans_cmd(trans_free)('trfree'),
        RequestHandler.trans_cmd(trans_io)('trio'),
        RequestHandler.trans_function(trans_internal)('int'),
        RequestHandler.trans_function(trans_data)('dat'),
        RequestHandler.trans_cmd(trans_json)('json', json=true),
        RequestHandler.trans_autocmd(vim_enter)(),
        RequestHandler.trans_cmd(trans_error)('error'),
    ),
    state_ctor=HsData,
)
dispatch_conf = DispatchConfig.cons(config)


# TODO test free trans function with invalid arg count
class DispatchSpec(SpecBase):
    '''
    run a free trans function $trans_free
    run an IO result from a free trans $io
    work on PluginState in internal trans $internal
    modify the state data $data
    json command args $json
    run an autocmd $autocmd
    error $error
    '''

    def trans_free(self) -> Expectation:
        helper = DispatchHelper.strict(config)
        result = helper.unsafe_run_a('command:trfree', args=('x',))
        return k(result) == 8

    @pending
    def io(self) -> Expectation:
        helper = DispatchHelper.strict(config)
        result = helper.unsafe_run_a('command:trio')
        return k(result) == 5

    def internal(self) -> Expectation:
        helper = DispatchHelper.strict(config)
        state, result = helper.unsafe_run('function:int')
        return k(result) == state.name

    def data(self) -> Expectation:
        helper = DispatchHelper.strict(config)
        state = helper.unsafe_run_s('function:dat')
        return k(state.data.counter) == 23

    def json(self) -> Expectation:
        helper = DispatchHelper.strict(config)
        js = '{ "number": 2, "name": "two", "items": ["1", "2", "3"] }'
        result = helper.unsafe_run_a('command:json', args=(7, 'one', *Lists.split(js, ' ')))
        return k(result) == 9

    def autocmd(self) -> Expectation:
        helper = DispatchHelper.strict(config)
        state = helper.unsafe_run_s('autocmd:vim_enter')
        return k(state.data.counter) == 19

    def error(self) -> Expectation:
        helper = DispatchHelper.strict(config)
        result = execute_request(helper.vim, helper.holder, 'command:error', (), True)
        return k(result) == 1


__all__ = ('DispatchSpec',)
