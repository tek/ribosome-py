from amino import do, curried, Do, __, _, Either
from amino.lenses.lens import lens

from ribosome.nvim.io import NS
from ribosome.plugin_state import PluginState
from ribosome.dispatch.mapping import Mapping, MapMode
from ribosome.nvim import NvimIO
from ribosome.trans.handler import FreeTrans
from ribosome.dispatch.component import Components


def mapping_handler(mapping: Mapping, components: Components) -> Either[str, FreeTrans]:
    return components.all.find_map(__.mappings.lift(mapping)).to_either(f'no handler for {mapping}')


def mapping_cmd(plugin: str, mapping: Mapping, mode: MapMode) -> NvimIO[None]:
    buf = '<buffer>' if mapping.buffer else ''
    keys = mapping.keys.replace('<', '<lt>')
    cmdline = f'''{mode.mnemonic}map {buf} {mapping.keys} :call {plugin}Map('{mapping.uuid}', '{keys}')<cr>'''
    return NvimIO.cmd(cmdline)


@do(NS[PluginState, None])
def activate_mapping(mapping: Mapping) -> Do:
    handler = yield NS.inspect_either(curried(mapping_handler)(mapping)).zoom(lens.components)
    yield NS.modify(__.append.active_mappings((mapping.uuid, handler)))
    plugin = yield NS.inspect(_.camelcase_name)
    yield NS.lift(mapping.modes.traverse(curried(mapping_cmd)(plugin, mapping), NvimIO))


__all__ = ('activate_mapping',)
