from amino import do, curried, Do, __, _, Either
from amino.lenses.lens import lens

from ribosome.nvim.io.state import NS
from ribosome.plugin_state import PluginState
from ribosome.dispatch.mapping import Mapping, MapMode
from ribosome.nvim.io.compute import NvimIO
from ribosome.trans.handler import TransF
from ribosome.dispatch.component import Components
from ribosome.nvim.api.command import nvim_command


def mapping_handler(mapping: Mapping, components: Components) -> Either[str, TransF]:
    return components.all.find_map(__.mappings.lift(mapping)).to_either(f'no handler for {mapping}')


def mapping_cmd(plugin: str, mapping: Mapping, mode: MapMode) -> NvimIO[None]:
    buf = '<buffer>' if mapping.buffer else ''
    keys = mapping.keys.replace('<', '<lt>')
    rhs = f''':call {plugin}Map('{mapping.uuid}', '{keys}')<cr>'''
    return nvim_command(
        f'{mode.mnemonic}map',
        buf,
        mapping.keys,
        rhs,
    )


@do(NS[PluginState, None])
def activate_mapping(mapping: Mapping) -> Do:
    handler = yield NS.inspect_either(curried(mapping_handler)(mapping)).zoom(lens.components)
    yield NS.modify(__.append.active_mappings((mapping.uuid, handler)))
    plugin = yield NS.inspect(_.camelcase_name)
    yield NS.lift(mapping.modes.traverse(curried(mapping_cmd)(plugin, mapping), NvimIO))


__all__ = ('activate_mapping',)
