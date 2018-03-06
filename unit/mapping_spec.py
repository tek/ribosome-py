from kallikrein import Expectation, k
from kallikrein.matchers import contain
from kallikrein.matchers.start_with import start_with
from kallikrein.matchers.maybe import be_just

from amino import do, Do, __, Map, List, curried, Either, _, Dat
from amino.boolean import true
from amino.lenses.lens import lens

from ribosome.trans.api import trans
from ribosome.nvim.io import NS
from ribosome.test.integration.run import DispatchHelper
from ribosome.nvim import NvimIO
from ribosome.test.config import default_config_name
from ribosome.test.integration.default import ExternalSpec
from ribosome.request.handler.handler import RequestHandler
from ribosome.plugin_state import PluginState
from ribosome.dispatch.component import Component, Components, ComponentData
from ribosome.config.config import Config
from ribosome.dispatch.mapping import Mappings, Mapping, mapmode, MapMode
from ribosome.trans.handler import FreeTrans

keys = 'gs'
gs_mapping = Mapping.cons('gs', true, List(mapmode.Normal(), mapmode.Visual()))


class CData(Dat['CData']):

    @staticmethod
    def cons(a: int=13) -> 'CData':
        return CData(a)

    def __init__(self, a: int) -> None:
        self.a = a


def mapping_handler(mapping: Mapping, components: Components) -> Either[str, FreeTrans]:
    return components.all.find_map(__.mappings.lift(mapping)).to_either(f'no handler for {mapping}')


def mapping_cmd(plugin: str, mapping: Mapping, mode: MapMode) -> NvimIO[None]:
    buf = '<buffer>' if mapping.buffer else ''
    return NvimIO.cmd(
        f'''{mode.mnemonic}map {buf} {mapping.keys} :call {plugin}Map('{mapping.uuid}', '{mapping.keys}')'''
    )


@do(NS[PluginState, None])
def activate_mapping(mapping: Mapping) -> Do:
    handler = yield NS.inspect_either(curried(mapping_handler)(mapping)).zoom(lens.components)
    yield NS.modify(__.append.active_mappings((mapping.uuid, handler)))
    plugin = yield NS.inspect(_.camelcase_name)
    yield NS.lift(mapping.modes.traverse(curried(mapping_cmd)(plugin, mapping), NvimIO))


@trans.free.unit(trans.st)
@do(NS[ComponentData[None, CData], None])
def handle_map() -> Do:
    yield NS.modify(lens.comp.a.set(27))


@trans.free.unit(trans.st)
@do(NS[PluginState, None])
def setup_map() -> Do:
    yield activate_mapping(gs_mapping).zoom(lens.main)
    yield NS.unit


component = Component.cons(
    'main',
    state_ctor=CData.cons,
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
        helper = DispatchHelper.nvim(config, self.vim, 'main')
        @do(NvimIO[None])
        def run() -> Do:
            (s, a) = yield helper.run_s('function:setup_map', args=())
            (s1, b) = yield helper.set.state(s.state).run_s('function:map', args=(str(gs_mapping.uuid), 'gs'))
            maps = yield NvimIO.delay(__.cmd_output('map <buffer>'))
            return s1.state.component_data.lift('main'), maps
        data, maps = run().unsafe(self.vim)
        return (
            k(maps).must(contain(start_with(f'x  {keys}')) & contain(start_with(f'n  {keys}'))) &
            (k(data / _.a).must(be_just(27)))
        )


__all__ = ('MappingSpec',)
