from typing import Generic, TypeVar, Callable

from amino import Dat, ADT, List, Maybe, Nil

from ribosome.util.menu.prompt.data import InputChar, PromptState, InputState
from ribosome.nvim.io.state import NS
from ribosome.compute.prog import Prog

A = TypeVar('A')
B = TypeVar('B')
C = TypeVar('C')


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
    def cons(lines: List[MenuLine[A]]=Nil, selected: int=None) -> 'MenuContent[A]':
        return MenuContent(lines, Maybe.optional(selected))

    def __init__(self, lines: List[MenuLine[A]], selected: Maybe[int]) -> None:
        self.lines = lines
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


class MenuRedraw(MenuAction):

    def __init__(self, content: MenuContent) -> None:
        self.content = content


class MenuUnit(MenuAction):
    pass


class MenuState(Generic[A, B], Dat['MenuState[A, B]']):

    @staticmethod
    def cons(
            state: A,
            content: MenuContent[B]=None,
    ) -> 'MenuState[A, B]':
        return MenuState(
            state,
            content or MenuContent.cons(),
        )

    def __init__(self, state: A, content: MenuContent[B]) -> None:
        self.state = state
        self.content = content


class MenuConfig(Generic[A, B, C], Dat['MenuConfig[A, B, C]']):

    @staticmethod
    def cons(
            handle_input: Callable[[InputChar], NS[InputState[MenuState[A, B], C], MenuAction]],
            name: str='',
    ) -> 'MenuConfig[A]':
        return MenuConfig(
            handle_input,
            name,
        )

    def __init__(
            self,
            handle_input: Callable[[InputChar], NS[InputState[MenuState[A, B], C], MenuAction]],
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
           'MenuPrompt', 'MenuRedraw', 'MenuUnit',)
