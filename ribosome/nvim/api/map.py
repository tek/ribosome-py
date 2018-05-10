from amino import do, Do

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.command import nvim_command_output


@do(NvimIO[str])
def show_mappings() -> Do:
    lines = yield nvim_command_output('map')
    return lines.join_lines


__all__ = ('show_mappings',)
