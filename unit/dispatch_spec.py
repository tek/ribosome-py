from kallikrein import Expectation, k
from kallikrein.matchers.maybe import be_just
from kallikrein.matchers.length import have_length

from amino.test.spec import SpecBase
from amino import Lists, List, _, IO, __, Right
from amino.boolean import true
from amino.dat import Dat, ADT
from amino.state import State

from ribosome.trans.api import trans
from ribosome.plugin_state import PluginState, DispatchConfig
from ribosome.request.handler.handler import RequestHandler
from ribosome.nvim.io import NS
from ribosome.test.integration.run import DispatchHelper
from ribosome.config.config import Config

specimen = Lists.random_string()


class HsData(Dat['HsData']):

    def __init__(self, counter: int=7) -> None:
        self.counter = counter


@trans.free.result()
def trans_free(a: int, b: str='b') -> int:
    return 8


@trans.free.result(trans.io)
def trans_io() -> IO[int]:
    return IO.pure(5)


# TODO allow args here
@trans.free.result(trans.st)
def trans_internal() -> NS[PluginState, str]:
    return NS.inspect(_.name)


@trans.free.unit(trans.st)
def trans_data() -> NS[HsData, None]:
    return NS.modify(__.set.counter(23))


class JData(ADT['JData']):

    def __init__(self, number: int, name: str, items: List[str]) -> None:
        self.number = number
        self.name = name
        self.items = items


@trans.free.result()
def trans_json(a: int, b: str, data: JData) -> int:
    return data.number + a


@trans.free.unit(trans.st)
def vim_enter() -> State[HsData, None]:
    return State.modify(__.copy(counter=19))


config = Config.cons(
    'hs',
    request_handlers=List(
        RequestHandler.trans_cmd(trans_free)('trfree'),
        RequestHandler.trans_cmd(trans_io)('trio'),
        RequestHandler.trans_function(trans_internal)('int'),
        RequestHandler.trans_function(trans_data)('dat'),
        RequestHandler.trans_cmd(trans_json)('json', json=true),
        RequestHandler.trans_autocmd(vim_enter)(),
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
    '''

    def trans_free(self) -> Expectation:
        helper = DispatchHelper.strict(config)
        result = helper.unsafe_run_a('command:trfree', args=('x',))
        return k(result) == 8

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


__all__ = ('DispatchSpec',)
