from typing import TypeVar, Callable, Generic

from amino import do, Do, ADT, List
from amino.case import Case
from amino.lenses.lens import lens

from ribosome.util.menu.data import Menu, MenuAction, MenuConfig, MenuState, MenuLine, MenuContent, MenuRedraw
from ribosome.util.menu.prompt.data import (InputChar, InputState, PromptUpdate, PromptUpdateChar, PromptUpdateConsumer,
                                            PrintableChar, SpecialChar, PromptUpdateInit)
from ribosome.nvim.io.state import NS

A = TypeVar('A')
B = TypeVar('B')
C = TypeVar('C')
D = TypeVar('D')
E = TypeVar('E')


class AutoUpdate(Generic[A, B], ADT['AutoUpdate[A, B]']):
    pass


class AutoUpdateRefresh(AutoUpdate[A, B]):

    def __init__(self, lines: List[MenuLine[B]]) -> None:
        self.lines = lines


class AutoUpdateConsumer(AutoUpdate[A, B]):

    def __init__(self, data: A) -> None:
        self.data = data


AutoS = NS[InputState[MenuState[A, B], AutoUpdate[C, D]], E]


class auto_update(Case[AutoUpdate[C, D], AutoS[A, B, C, D, MenuAction]], alg=AutoUpdate):

    def __init__(self, process: Callable[[PromptUpdate[AutoUpdate[C, D]]], AutoS[A, B, C, D, MenuAction]]) -> None:
        self.process = process

    @do(AutoS[A, B, C, D, MenuAction])
    def refresh(self, update: AutoUpdateRefresh[C, D]) -> Do:
        yield NS.unit

    @do(AutoS[A, B, C, D, MenuAction])
    def consumer(self, update: AutoUpdateConsumer[C, D]) -> Do:
        yield self.process(PromptUpdateConsumer(update))


@do(AutoS[A, B, C, D, MenuAction])
def filter_menu(char: InputChar) -> Do:
    lines = yield NS.inspect(lambda a: a.data.content.lines)
    filter = yield NS.inspect(lambda a: a.prompt.line)
    filtered = lines.filter(lambda a: filter in a.text)
    yield NS.modify(lens.data.content.filtered.set(filtered))
    content = yield NS.inspect(lambda a: a.data.content)
    return MenuRedraw(content)


class auto_menu_input_char(Case[InputChar, AutoS[A, B, C, D, MenuAction]], alg=InputChar):

    def __init__(self, process: Callable[[PromptUpdate[AutoUpdate[C, D]]], AutoS[A, B, C, D, MenuAction]]) -> None:
        self.process = process

    def printable(self, char: PrintableChar) -> AutoS[A, B, C, D, MenuAction]:
        return filter_menu(char)

    def special(self, char: SpecialChar) -> AutoS[A, B, C, D, MenuAction]:
        yield self.process(PromptUpdateChar(char))


class auto_menu_handle(Case[PromptUpdate[AutoUpdate[C, D]], AutoS[A, B, C, D, MenuAction]], alg=PromptUpdate):

    def __init__(self, process: Callable[[PromptUpdate[AutoUpdate[C, D]]], AutoS[A, B, C, D, MenuAction]]) -> None:
        self.process = process

    @do(NS[InputState[MenuState[A, B], AutoUpdate[C, D]], MenuAction])
    def init(self, update: PromptUpdateInit[AutoUpdate[C, D]]) -> Do:
        content = yield NS.inspect(lambda a: a.data.content)
        yield NS.pure(MenuRedraw(content))

    @do(NS[InputState[MenuState[A, B], AutoUpdate[C, D]], MenuAction])
    def char(self, update: PromptUpdateChar[AutoUpdate[C, D]]) -> Do:
        yield auto_menu_input_char(self.process)(update.char)

    @do(NS[InputState[MenuState[A, B], AutoUpdate[C, D]], MenuAction])
    def consumer(self, update: PromptUpdateConsumer[AutoUpdate[C, D]]) -> Do:
        yield auto_update(self.process)(update.data)


def auto_menu(
        state: A,
        content: MenuContent[B],
        process: Callable[[PromptUpdate[AutoUpdate[C, D]]], AutoS[A, B, C, D, MenuAction]],
        name: str,
) -> Menu:
    handle = auto_menu_handle(process)
    config = MenuConfig.cons(handle, name)
    return Menu.cons(config, MenuState.cons(state, content))


__all__ = ('auto_menu',)
