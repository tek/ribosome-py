from typing import TypeVar

from amino import do, Do, Map, List, Maybe
from amino.lenses.lens import lens
from amino.logging import module_log

from ribosome.util.menu.auto.data import AutoS
from ribosome.nvim.io.state import NS
from ribosome.util.menu.data import MenuPrompt, MenuUpdateCursor, MenuLine, visible_menu_indexes, MenuState, MenuQuit
from ribosome.util.menu.prompt.data import PromptPassthrough, InputState
from ribosome.util.menu.prompt.run import prompt_state_fork_strict

log = module_log()
A = TypeVar('A')
S = TypeVar('S')
ML = TypeVar('ML')
U = TypeVar('U')


def menu_cmd_esc() -> AutoS[S, ML, U]:
    return prompt_state_fork_strict(
        MenuPrompt(PromptPassthrough()),
        MenuQuit(),
    )


@do(NS[InputState[MenuState[S, ML, U], U], int])
def menu_direction() -> Do:
    bottom = yield NS.inspect(lambda a: a.data.config.bottom)
    return -1 if bottom else 1


@do(AutoS[S, ML, U])
def menu_cmd_scroll(offset: int) -> Do:
    direction = yield menu_direction()
    visible_indexes = yield NS.inspect(lambda a: visible_menu_indexes(a.data.content))
    count = visible_indexes.length
    yield NS.modify(lens.data.cursor.modify(lambda a: (a + direction * offset) % count))
    return MenuUpdateCursor()


def menu_cmd_up() -> AutoS[S, ML, U]:
    return menu_cmd_scroll(-1)


def menu_cmd_down() -> AutoS[S, ML, U]:
    return menu_cmd_scroll(1)


def toggle_selected(lines: List[MenuLine[A]], index: int) -> Maybe[List[MenuLine[A]]]:
    return lines.modify_at(index, lambda b: b.mod.selected(lambda c: not c))


visibility_error = 'broken visibility map for menu'


@do(AutoS[S, ML, U])
def menu_cmd_select_cursor() -> Do:
    cursor = yield NS.inspect(lambda a: a.cursor)
    content = yield NS.inspect(lambda a: a.data.content)
    visible_indexes = visible_menu_indexes(content)
    index = yield NS.from_maybe(visible_indexes.lift(cursor), lambda: visibility_error)
    toggled = yield NS.from_maybe(toggle_selected(content.lines, index), lambda: visibility_error)
    yield NS.modify(lens.data.content.lines.set(toggled))
    return MenuUpdateCursor()


@do(AutoS[S, ML, U])
def menu_cmd_select_all() -> Do:
    yield NS.modify(lens.data.content.lines.modify(lambda a: a.map(lambda b: b.mod.selected(lambda c: not c))))
    return MenuUpdateCursor()


builtin_mappings = Map({
    '<esc>': menu_cmd_esc,
    'q': menu_cmd_esc,
    'k': menu_cmd_up,
    '<c-k>': menu_cmd_up,
    'j': menu_cmd_down,
    '<c-j>': menu_cmd_down,
    '<space>': menu_cmd_select_cursor,
    '*': menu_cmd_select_all,
})

__all__ = ('builtin_mappings',)
