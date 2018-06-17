from typing import Callable

from amino import do, curried, Do, __, _, Either
from amino.lenses.lens import lens
from amino.logging import module_log

from ribosome.nvim.io.state import NS
from ribosome.data.plugin_state import PluginState
from ribosome.nvim.io.compute import NvimIO
from ribosome.compute.program import Program
from ribosome.config.component import Components
from ribosome.nvim.api.command import nvim_command
from ribosome.data.mapping import Mapping, MapMode

log = module_log()


def mapping_handler(mapping: Mapping) -> Callable[[Components], Either[str, Program]]:
    def mapping_handler(components: Components) -> Either[str, Program]:
        return components.all.find_map(__.mappings.lift(mapping)).to_either(f'no handler for {mapping}')
    return mapping_handler


def mapping_cmd(plugin: str, mapping: Mapping, mode: MapMode) -> NvimIO[None]:
    buf = '<buffer>' if mapping.buffer else ''
    keys = mapping.keys.replace('<', '<lt>')
    rhs = f''':call {plugin}Map('{mapping.ident}', '{keys}')<cr>'''
    return nvim_command(
        f'{mode.mnemonic}map',
        buf,
        '<silent>',
        mapping.keys,
        rhs,
    )


@do(NS[PluginState, None])
def activate_mapping(mapping: Mapping) -> Do:
    handler = yield NS.inspect_either(mapping_handler(mapping)).zoom(lens.components)
    yield NS.modify(__.append.active_mappings((mapping.ident, handler)))
    plugin = yield NS.inspect(_.camelcase_name)
    yield NS.lift(mapping.modes.traverse(curried(mapping_cmd)(plugin, mapping), NvimIO))


__all__ = ('activate_mapping',)
