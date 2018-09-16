from amino import do, Do

from ribosome.util.menu.data import Menu
from ribosome.nvim.io.compute import NvimIO
from ribosome.util.menu.prompt.run import prompt


@do(NvimIO[None])
def run_menu(menu: Menu) -> Do:
    yield prompt(menu.config.keypress, menu.config.initial)


__all__ = ('run_menu',)
