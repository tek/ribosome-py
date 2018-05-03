from typing import Any

from kallikrein import Expectation, k, pending

from amino.test.spec import SpecBase
from amino import Lists, List, _, IO, __, do, Do, Just
from amino.boolean import true
from amino.dat import Dat, ADT
from amino.json.decoder import decode_json_type

from ribosome.compute.api import prog
from ribosome.data.plugin_state import PluginState
from ribosome.request.handler.handler import rpc
from ribosome.nvim.io.state import NS
from ribosome.test.integration.run import RequestHelper
from ribosome.config.config import Config
from ribosome.request.execute import execute_request
from ribosome.nvim.io.api import N
from ribosome.request.handler.prefix import Plain

specimen = Lists.random_string()


class HsData(Dat['HsData']):

    def __init__(self, counter: int=7) -> None:
        self.counter = counter


@prog
def trans_free(a: int, b: str='b') -> NS[None, int]:
    return NS.pure(8)


@prog
@do(NS[HsData, IO[int]])
def trans_io() -> Do:
    return NS.pure(IO.pure(5))


# TODO allow args here
@prog
def trans_internal() -> NS[PluginState, str]:
    return NS.inspect(_.basic.name)


@prog.unit
def trans_data() -> NS[HsData, None]:
    return NS.modify(__.set.counter(23))


class JData(Dat['JData']):

    def __init__(self, number: int, name: str, items: List[str]) -> None:
        self.number = number
        self.name = name
        self.items = items


@prog
def trans_json(a: int, b: str, data: JData) -> NS[HsData, int]:
    return NS.pure(data.number + a)


@prog.unit
@do(NS[HsData, None])
def vim_enter() -> Do:
    yield NS.modify(__.copy(counter=19))


@prog
def trans_error() -> NS[HsData, int]:
    return NS.lift(N.error('error'))


config: Config[HsData, Any] = Config.cons(
    'hs',
    rpc=List(
        rpc.write(trans_free),
        rpc.write(trans_io),
        rpc.write(trans_internal),
        rpc.write(trans_data),
        rpc.write(trans_json).conf(json=true),
        rpc.autocmd(vim_enter).conf(prefix=Plain()),
        rpc.write(trans_error),
    ),
    state_ctor=HsData,
)


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
        helper = RequestHelper.strict(config)
        result = helper.unsafe_run_a('trans_free', args=('x',))
        return k(result) == 8

    @pending
    def io(self) -> Expectation:
        helper = RequestHelper.strict(config)
        result = helper.unsafe_run_a('trans_io')
        return k(result) == 5

    def internal(self) -> Expectation:
        helper = RequestHelper.strict(config)
        state, result = helper.unsafe_run('trans_internal')
        return k(result) == state.basic.name

    def data(self) -> Expectation:
        helper = RequestHelper.strict(config)
        state = helper.unsafe_run_s('trans_data')
        return k(state.data.counter) == 23

    def json(self) -> Expectation:
        helper = RequestHelper.strict(config)
        js = '{ "number": 2, "name": "two", "items": ["1", "2", "3"] }'
        result = helper.unsafe_run_a('trans_json', args=(7, 'one', *Lists.split(js, ' ')))
        return k(result) == 9

    def autocmd(self) -> Expectation:
        helper = RequestHelper.strict(config)
        state = helper.unsafe_run_s('vim_enter')
        return k(state.data.counter) == 19

    def error(self) -> Expectation:
        helper = RequestHelper.strict(config)
        result = execute_request(helper.vim, helper.holder, 'error', (), True)
        return k(result) == 1


__all__ = ('DispatchSpec',)
