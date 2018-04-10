from kallikrein import Expectation, k
from kallikrein.matchers import contain
from kallikrein.matchers.start_with import start_with
from kallikrein.matchers.maybe import be_just

from amino import do, Do, __, Map, List, _, Dat
from amino.boolean import true
from amino.lenses.lens import lens

from ribosome.compute.api import prog
from ribosome.nvim.io.state import NS
from ribosome.test.integration.run import RequestHelper
from ribosome.nvim.io.compute import NvimIO
from ribosome.test.config import default_config_name
from ribosome.test.integration.default import ExternalSpec
from ribosome.request.handler.handler import RequestHandler
from ribosome.data.plugin_state import PluginState
from ribosome.config.component import Component, ComponentData
from ribosome.config.config import Config, NoData
from ribosome.nvim.api.command import nvim_command_output
from ribosome.config.settings import Settings
from ribosome.data.mapping import Mappings, Mapping, mapmode
from ribosome.components.internal.mapping import activate_mapping

keys = 'gs'
gs_mapping = Mapping.cons('gs', true, List(mapmode.Normal(), mapmode.Visual()))


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
@do(NS[PluginState[Settings, NoData, None], None])
def setup_map() -> Do:
    yield activate_mapping(gs_mapping)
    yield NS.unit


component = Component.cons(
    'main',
    state_type=CData,
    request_handlers=List(
        RequestHandler.trans_function(setup_map)(),
        RequestHandler.trans_function(handle_map)(json=true)
    ),
    mappings=Mappings.cons(
        Map({gs_mapping: handle_map}),
    )
)
config = Config.cons(
    name=default_config_name,
    prefix=default_config_name,
    components=Map(main=component),
)


class MappingSpec(ExternalSpec):
    '''
    map a key buffer-local $buffer
    '''

    def buffer(self) -> Expectation:
        helper = RequestHelper.nvim(config, self.vim, 'main')
        @do(NvimIO[None])
        def run() -> Do:
            s = yield helper.run_s('function:setup_map', args=())
            s1 = yield helper.set.state(s).run_s('function:map', args=(str(gs_mapping.uuid), 'gs'))
            maps = yield nvim_command_output('map <buffer>')
            return s1.component_data.lift(CData), maps
        data, maps = run().unsafe(self.vim)
        return (
            k(maps).must(contain(start_with(f'x  {keys}')) & contain(start_with(f'n  {keys}'))) &
            (k(data / _.a).must(be_just(27)))
        )


__all__ = ('MappingSpec',)
