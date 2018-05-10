from kallikrein import Expectation, k, pending
from kallikrein.matchers import contain
from kallikrein.matchers.start_with import start_with
from kallikrein.matchers.maybe import be_just

from amino import do, Do, __, Map, List, _, Dat
from amino.boolean import true
from amino.lenses.lens import lens
from amino.test.spec import SpecBase

from ribosome.compute.api import prog
from ribosome.nvim.io.state import NS
from ribosome.nvim.io.compute import NvimIO
from ribosome.test.config import default_config_name, TestConfig
from ribosome.rpc.api import rpc
from ribosome.data.plugin_state import PluginState, PS
from ribosome.config.component import Component, ComponentData
from ribosome.config.config import Config, NoData
from ribosome.nvim.api.command import nvim_command_output
from ribosome.data.mapping import Mappings, Mapping, mapmode
from ribosome.components.internal.mapping import activate_mapping
from ribosome.test.prog import request
from ribosome.test.unit import unit_test
from ribosome.test.integration.external import external_state_test

keys = 'gs'
gs_mapping = Mapping.cons('test-mapping', 'gs', true, List(mapmode.Normal(), mapmode.Visual()))


class CData(Dat['CData']):

    @staticmethod
    def cons(a: int=13) -> 'CData':
        return CData(a)

    def __init__(self, a: int) -> None:
        self.a = a


@prog.unit
@do(NS[ComponentData[NoData, CData], None])
def handle_map() -> Do:
    yield NS.modify(lens.comp.a.set(27))


@prog.unit
@do(NS[PluginState[NoData, None], None])
def setup_map() -> Do:
    yield activate_mapping(gs_mapping)
    yield NS.unit


component: Component = Component.cons(
    'main',
    state_type=CData,
    rpc=List(
        rpc.write(setup_map),
        rpc.write(handle_map).conf(json=true)
    ),
    mappings=Mappings.cons(
        (gs_mapping, handle_map),
    )
)
config: Config = Config.cons(
    name=default_config_name,
    prefix=default_config_name,
    components=Map(main=component),
)
test_config = TestConfig.cons(config, components=List('main'))


@do(NS[PS, Expectation])
def buffer_spec() -> Do:
    yield request('setup_map')
    yield request('map', gs_mapping.ident, 'gs')
    maps = yield NS.lift(nvim_command_output('map <buffer>'))
    data = yield NS.inspect(lambda s: s.data_by_type(CData))
    return (
        k(maps).must(contain(start_with(f'x  {keys}')) & contain(start_with(f'n  {keys}'))) &
        (k(data.a) == 27)
    )


# FIXME
class MappingSpec(SpecBase):
    '''
    map a key buffer-local $buffer
    '''

    def buffer(self) -> Expectation:
        return external_state_test(test_config, buffer_spec)


__all__ = ('MappingSpec',)
