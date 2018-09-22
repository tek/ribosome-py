from typing import Generic, TypeVar, Callable

from amino import Dat, ADT, List, Nil

from ribosome.util.menu.prompt.data import PromptState, InputState, PromptUpdate
from ribosome.nvim.io.state import NS
from ribosome.compute.prog import Prog

A = TypeVar('A')
B = TypeVar('B')
C = TypeVar('C')
S = TypeVar('S')
ML = TypeVar('ML')


class MenuLine(Generic[A], Dat['MenuLine[A]']):

    @staticmethod
    def cons(
            text: str,
            meta: A,
    ) -> 'MenuLine[A]':
        return MenuLine(
            text,
            meta,
        )

    def __init__(self, text: str, meta: A) -> None:
        self.text = text
        self.meta = meta


class MenuContent(Generic[A], Dat['MenuContent[A]']):

    @staticmethod
    def cons(
            lines: List[MenuLine[A]]=Nil,
            filtered: List[MenuLine[A]]=Nil,
            selected: List[int]=Nil,
    ) -> 'MenuContent[A]':
        return MenuContent(lines, filtered, selected)

    def __init__(self, lines: List[MenuLine[A]], filtered: List[MenuLine[A]], selected: List[int]) -> None:
        self.lines = lines
        self.filtered = filtered
        self.selected = selected


class MenuAction(ADT['MenuAction']):
    pass


class MenuQuit(MenuAction):
    pass


class MenuQuitWith(MenuAction):

    def __init__(self, prog: Prog[None]) -> None:
        self.prog = prog


class MenuPrompt(MenuAction):

    def __init__(self, state: PromptState) -> None:
        self.state = state


class MenuUpdateLines(MenuAction):

    def __init__(self, content: MenuContent) -> None:
        self.content = content


class MenuUpdateCursor(MenuAction):
    pass


class MenuUnit(MenuAction):
    pass


class MenuState(Generic[S, ML], Dat['MenuState[S, ML]']):

    @staticmethod
    def cons(
            state: S,
            content: MenuContent[ML]=None,
            cursor: int=0,
    ) -> 'MenuState[A, B]':
        return MenuState(
            state,
            content or MenuContent.cons(),
            cursor,
        )

    def __init__(self, state: S, content: MenuContent[ML], cursor: int) -> None:
        self.state = state
        self.content = content
        self.cursor = cursor


class MenuConfig(Generic[A, B, C], Dat['MenuConfig[A, B, C]']):

    @staticmethod
    def cons(
            handle_input: Callable[[PromptUpdate[C]], NS[InputState[MenuState[A, B], C], MenuAction]],
            name: str='',
    ) -> 'MenuConfig[A, B, C]':
        return MenuConfig(
            handle_input,
            name,
        )

    def __init__(
            self,
            handle_input: Callable[[PromptUpdate[C]], NS[InputState[MenuState[A, B], C], MenuAction]],
            name: str,
    ) -> None:
        self.handle_input = handle_input
        self.name = name


class Menu(Generic[A, B, C], Dat['Menu[A, B, C]']):

    @staticmethod
    def cons(
            config: MenuConfig[A, B, C],
            state: MenuState[A, B],
    ) -> 'Menu':
        return Menu(
            config,
            state,
        )

    def __init__(self, config: MenuConfig[A, B, C], state: MenuState[A, B]) -> None:
        self.config = config
        self.state = state


__all__ = ('MenuConfig', 'MenuLine', 'MenuState', 'Menu', 'MenuContent', 'MenuAction', 'MenuQuit', 'MenuQuitWith',
           'MenuPrompt', 'MenuUpdateLines', 'MenuUnit', 'MenuUpdateCursor',)
