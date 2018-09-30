from typing import TypeVar

from amino import do, Do, Map, List, Maybe
from amino.lenses.lens import lens

from ribosome.util.menu.auto.data import AutoS
from ribosome.nvim.io.state import NS
from ribosome.util.menu.data import MenuPrompt, MenuUpdateCursor, MenuLine
from ribosome.util.menu.prompt.data import PromptPassthrough

A = TypeVar('A')


# TODO fork by prompt state. if in passthrough, esc should quit
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


def toggle_selected(lines: List[MenuLine[A]], index: int) -> Maybe[List[MenuLine[A]]]:
    return lines.modify_at(index, lambda b: b.mod.selected(lambda c: not c))


visibility_error = 'broken visibility map for menu'


@do(AutoS)
def menu_cmd_select_cursor() -> Do:
    cursor = yield NS.inspect(lambda a: a.cursor)
    content = yield NS.inspect(lambda a: a.data.content)
    index = yield NS.from_maybe(content.visible.lift(cursor), lambda: visibility_error)
    toggled = yield NS.from_maybe(toggle_selected(content.lines, index), lambda: visibility_error)
    yield NS.modify(lens.data.content.lines.set(toggled))
    return MenuUpdateCursor()


@do(AutoS)
def menu_cmd_select_all() -> Do:
    yield NS.modify(lens.data.content.lines.modify(lambda a: a.map(lambda b: b.mod.selected(lambda c: not c))))
    return MenuUpdateCursor()


builtin_mappings = Map({
    '<esc>': menu_cmd_esc,
    'k': menu_cmd_up,
    'j': menu_cmd_down,
    '<space>': menu_cmd_select_cursor,
    '*': menu_cmd_select_all,
})

__all__ = ('builtin_mappings',)
