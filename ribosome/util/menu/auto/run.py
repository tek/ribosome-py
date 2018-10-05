from typing import TypeVar, Callable

from amino import do, Do, Map, Nil, List, Just, Nothing
from amino.case import Case
from amino.lenses.lens import lens
from amino.logging import module_log

from ribosome.util.menu.data import (Menu, MenuConfig, MenuState, MenuContent, MenuUpdateLines, MenuLine,
                                     selected_lines, MenuUnit)
from ribosome.util.menu.prompt.data import (InputChar, InputState, PromptUpdate, PromptUpdateChar, PromptUpdateConsumer,
                                            PrintableChar, SpecialChar, PromptUpdateInit, PromptEcho)
from ribosome.nvim.io.state import NS
from ribosome.util.menu.auto.data import AutoUpdate, AutoUpdateRefresh, AutoUpdateConsumer, AutoState, AutoS
from ribosome.util.menu.auto.cmd import builtin_mappings

log = module_log()
A = TypeVar('A')
B = TypeVar('B')
C = TypeVar('C')
S = TypeVar('S')
ML = TypeVar('ML')
U = TypeVar('U')


@do(NS[InputState[A, B], C])
def prompt_state_fork(
        echo: Callable[[], NS[InputState[A, B], C]],
        passthrough: Callable[[], NS[InputState[A, B], C]],
) -> Do:
    state = yield NS.inspect(lambda a: a.state)
    yield (
        echo()
        if isinstance(state, PromptEcho) else
        passthrough()
    )


class auto_update(Case[AutoUpdate[U, ML], AutoS], alg=AutoUpdate):

    @do(AutoS)
    def refresh(self, update: AutoUpdateRefresh[U, ML]) -> Do:
        yield NS.unit

    @do(AutoS)
    def consumer(self, update: AutoUpdateConsumer[U, ML]) -> Do:
        consumer = yield NS.inspect(lambda a: a.data.state.consumer)
        yield consumer(PromptUpdateConsumer(update))


@do(AutoS)
def filter_menu(char: str) -> Do:
    lines = yield NS.inspect(lambda a: a.data.content.lines)
    filter = yield NS.inspect(lambda a: a.prompt.line)
    updated_lines = lines.map(lambda a: a.set.visible(filter in a.text))
    visible = lines.with_index.collect(lambda a: Just(a[0]) if a[1].visible else Nothing)
    yield NS.modify(lens.data.content.modify(lambda a: a.copy(lines=updated_lines, visible=Just(visible))))
    content = yield NS.inspect(lambda a: a.data.content)
    return MenuUpdateLines(content)


@do(AutoS)
def menu_mapping(code: str, char: InputChar) -> Do:
    mappings = yield NS.inspect(lambda a: a.data.state.mappings)
    consumer = yield NS.inspect(lambda a: a.data.state.consumer)
    yield mappings.lift(code).map(lambda a: a()).get_or(consumer, PromptUpdateChar(char))


class auto_menu_input_char(Case[InputChar, AutoS[U, ML, S]], alg=InputChar):

    def printable(self, char: PrintableChar) -> AutoS:
        return prompt_state_fork(lambda: filter_menu(char.char), lambda: menu_mapping(char.char, char))

    def special(self, char: SpecialChar) -> AutoS:
        return menu_mapping(char.char, char)


class auto_menu_handle(Case[PromptUpdate[AutoUpdate[U, ML]], AutoS[U, ML, S]], alg=PromptUpdate):

    @do(AutoS)
    def init(self, update: PromptUpdateInit[AutoUpdate[U, ML]]) -> Do:
        content = yield NS.inspect(lambda a: a.data.content)
        yield NS.pure(MenuUpdateLines(content))

    @do(AutoS)
    def char(self, update: PromptUpdateChar[AutoUpdate[U, ML]]) -> Do:
        yield auto_menu_input_char.match(update.char)

    @do(AutoS)
    def consumer(self, update: PromptUpdateConsumer[AutoUpdate[U, ML]]) -> Do:
        yield auto_update.match(update.data)


def no_process(update: PromptUpdate[AutoUpdate[U, ML]]) -> AutoS:
    return NS.pure(MenuUnit())


def auto_menu(
        state: S,
        content: MenuContent[ML],
        name: str,
        mappings: Map[str, Callable[[], AutoS]]=Map(),
        consumer: Callable[[PromptUpdate[AutoUpdate[U, ML]]], AutoS]=no_process,
) -> Menu[AutoState[U, ML, S], ML, C]:
    config: MenuConfig[AutoState[U, ML, S], ML, C] = MenuConfig.cons(auto_menu_handle.match, name)
    all_mappings = builtin_mappings ** mappings
    menu_state: MenuState[AutoState[U, ML, S], ML] = MenuState.cons(AutoState(consumer, state, all_mappings), content)
    return Menu.cons(config, menu_state)


@do(NS[InputState[MenuState[AutoState[U, ML, S], ML], AutoUpdate[U, ML]], List[MenuLine[ML]]])
def selected_menu_lines() -> Do:
    content = yield NS.inspect(lambda a: a.data.content)
    cursor = yield NS.inspect(lambda a: a.data.cursor)
    return selected_lines(content, cursor)


__all__ = ('auto_menu', 'selected_menu_lines',)
