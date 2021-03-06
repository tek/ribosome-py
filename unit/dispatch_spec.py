from typing import Any

from kallikrein import Expectation, k, pending

from amino.test.spec import SpecBase
from amino import Lists, List, _, IO, __, do, Do
from amino.boolean import true
from amino.dat import Dat

from ribosome.compute.api import prog
from ribosome.data.plugin_state import PluginState, PS
from ribosome.nvim.io.state import NS
from ribosome.config.config import Config
from ribosome.nvim.io.api import N
from ribosome.rpc.api import rpc
from ribosome.rpc.data.prefix_style import Plain
from ribosome.nvim.io.compute import NvimIO
from ribosome.test.unit import unit_test
from ribosome.test.prog import request
from ribosome.test.config import TestConfig

specimen = Lists.random_string()


class HsData(Dat['HsData']):

    def __init__(self, counter: int=7) -> None:
        self.counter = counter


@prog
def prog_free(a: int, b: str='b') -> NS[None, int]:
    return NS.pure(8)


@prog
@do(NS[HsData, IO[int]])
def prog_io() -> Do:
    return NS.pure(IO.pure(5))


# TODO allow args here
@prog
def prog_internal() -> NS[PluginState, str]:
    return NS.inspect(_.basic.name)


@prog.unit
def prog_data() -> NS[HsData, None]:
    return NS.modify(__.set.counter(23))


class JData(Dat['JData']):

    def __init__(self, number: int, name: str, items: List[str]) -> None:
        self.number = number
        self.name = name
        self.items = items


@prog
def prog_json(a: int, b: str, data: JData) -> NS[HsData, int]:
    return NS.pure(data.number + a)


@prog.unit
@do(NS[HsData, None])
def vim_enter() -> Do:
    yield NS.modify(__.copy(counter=19))


@prog
def prog_error() -> NS[HsData, int]:
    return NS.lift(N.error('error'))


config: Config[HsData, Any] = Config.cons(
    'hs',
    rpc=List(
        rpc.write(prog_free),
        rpc.write(prog_io),
        rpc.write(prog_internal),
        rpc.write(prog_data),
        rpc.write(prog_json).conf(json=true),
        rpc.autocmd(vim_enter).conf(prefix=Plain()),
        rpc.write(prog_error),
    ),
    state_ctor=HsData,
    internal_component=False,
)
test_config = TestConfig.cons(config)


@do(NS[PS, Expectation])
def json_spec() -> Do:
    js = '{ "number": 2, "name": "two", "items": ["1", "2", "3"] }'
    result = yield request('prog_json', 7, 'one', *Lists.split(js, ' '))
    return k(result) == List(9)


# TODO test free prog function with invalid arg count
class DispatchSpec(SpecBase):
    '''
    run a free prog function $prog_free
    run an IO result from a free prog $io
    work on PluginState in internal prog $internal
    modify the state data $data
    json command args $json
    run an autocmd $autocmd
    '''

    @pending
    def prog_free(self) -> Expectation:
        helper = RequestHelper.strict(config)
        result = helper.unsafe_run_a('prog_free', args=('x',))
        return k(result) == 8

    @pending
    def io(self) -> Expectation:
        helper = RequestHelper.strict(config)
        result = helper.unsafe_run_a('prog_io')
        return k(result) == 5

    @pending
    def internal(self) -> Expectation:
        helper = RequestHelper.strict(config)
        state, result = helper.unsafe_run('prog_internal')
        return k(result) == state.basic.name

    @pending
    def data(self) -> Expectation:
        helper = RequestHelper.strict(config)
        state = helper.unsafe_run_s('prog_data')
        return k(state.data.counter) == 23

    @pending
    def json(self) -> Expectation:
        return unit_test(test_config, json_spec)

    @pending
    def autocmd(self) -> Expectation:
        helper = RequestHelper.strict(config)
        state = helper.unsafe_run_s('vim_enter')
        return k(state.data.counter) == 19


__all__ = ('DispatchSpec',)
