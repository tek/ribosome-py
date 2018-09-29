from amino import do, Do, Map
from amino.lenses.lens import lens

from ribosome.util.menu.auto.data import AutoS
from ribosome.nvim.io.state import NS
from ribosome.util.menu.data import MenuPrompt, MenuUpdateCursor
from ribosome.util.menu.prompt.data import PromptPassthrough


# TODO fork by state. if in passthrough, esc should quit
@do(AutoS)
def menu_cmd_esc() -> Do:
    yield NS.pure(MenuPrompt(PromptPassthrough()))


@do(AutoS)
def menu_cmd_up() -> Do:
    yield NS.modify(lens.data.cursor.modify(lambda a: max(a - 1, 0)))
    return MenuUpdateCursor()


@do(AutoS)
def menu_cmd_down() -> Do:
    count = yield NS.inspect(lambda a: a.data.content.filtered.length)
    yield NS.modify(lens.data.cursor.modify(lambda a: min(a + 1, count)))
    return MenuUpdateCursor()


builtin_mappings = Map({
    '<esc>': menu_cmd_esc,
    'k': menu_cmd_up,
    'j': menu_cmd_down,
})

__all__ = ('builtin_mappings',)
