from typing import Generic, TypeVar, Callable, Any

from amino import Dat, ADT, List, Nil, Maybe, Lists
from amino.logging import module_log

from ribosome.util.menu.prompt.data import PromptState, InputState, PromptUpdate
from ribosome.nvim.io.state import NS
from ribosome.compute.prog import Prog
from ribosome.nvim.scratch import ScratchBuffer

log = module_log()
A = TypeVar('A')
B = TypeVar('B')
S = TypeVar('S')
ML = TypeVar('ML')
U = TypeVar('U')


class MenuLine(Generic[A], Dat['MenuLine[A]']):

    @staticmethod
    def cons(
            text: str,
            meta: A,
            visible: bool=True,
            selected: bool=False,
    ) -> 'MenuLine[A]':
        return MenuLine(
            text,
            meta,
            visible,
            selected,
        )

    def __init__(self, text: str, meta: A, visible: bool, selected: bool) -> None:
        self.text = text
        self.meta = meta
        self.visible = visible
        self.selected = selected


class MenuContent(Generic[A], Dat['MenuContent[A]']):

    @staticmethod
    def cons(
            lines: List[MenuLine[A]]=Nil,
            visible: List[int]=None,
    ) -> 'MenuContent[A]':
        return MenuContent(lines, Maybe.optional(visible))

    def __init__(self, lines: List[MenuLine[A]], visible: Maybe[List[int]]) -> None:
        self.lines = lines
        self.visible = visible


def visible_menu_indexes(content: MenuContent[A]) -> List[int]:
    return content.visible.get_or(Lists.range, len(content.lines))


def visible_lines(content: MenuContent[A]) -> List[MenuLine[A]]:
    return content.lines.filter(lambda a: a.visible)


def selected_lines(content: MenuContent[A], cursor: int) -> List[MenuLine[A]]:
    visible = visible_lines(content)
    selected = visible.filter(lambda a: a.selected)
    return (
        visible.lift(cursor).to_list
        if selected.empty else
        selected
    )


class MenuAction(ADT['MenuAction']):
    pass


class MenuQuit(MenuAction):
    pass


class MenuQuitWith(MenuAction):

    def __init__(self, next: Prog[None]) -> None:
        self.next = next


class MenuPrompt(MenuAction):

    def __init__(self, state: PromptState) -> None:
        self.state = state


class MenuUpdateLines(MenuAction):

    def __init__(self, content: MenuContent) -> None:
        self.content = content


class MenuUpdateCursor(MenuAction):
    pass


class MenuPush(MenuAction):

    def __init__(self, thunk: Callable[[ScratchBuffer], NS[Any, Prog[None]]]) -> None:
        self.thunk = thunk


class MenuPop(MenuAction):
    pass


class MenuUnit(MenuAction):
    pass


class MenuStackAction(ADT['MenuStackAction']):
    pass


class MenuStackQuit(MenuStackAction):
    pass


class MenuStackPush(MenuStackAction):

    def __init__(self, current: NS[Any, Prog[None]], thunk: NS[Any, Prog[None]]) -> None:
        self.current = current
        self.thunk = thunk


class MenuStackPop(MenuStackAction):
    pass


class MenuState(Generic[S, ML], Dat['MenuState[S, ML]']):

    @staticmethod
    def cons(
            state: S,
            content: MenuContent[ML]=None,
            cursor: int=0,
            next: MenuStackAction=MenuStackQuit(),
            result: Prog[None]=None,
    ) -> 'MenuState[S, ML]':
        return MenuState(
            state,
            content or MenuContent.cons(),
            cursor,
            next,
            Maybe.optional(result),
        )

    def __init__(
            self,
            state: S,
            content: MenuContent[ML],
            cursor: int,
            next: MenuStackAction,
            result: Maybe[Prog[None]],
    ) -> None:
        self.state = state
        self.content = content
        self.cursor = cursor
        self.next = next
        self.result = result


class MenuConfig(Generic[S, ML, U], Dat['MenuConfig[S, ML, U]']):

    @staticmethod
    def cons(
            handle_input: Callable[[PromptUpdate[U]], NS[InputState[MenuState[S, ML], U], MenuAction]],
            name: str='',
    ) -> 'MenuConfig[S, ML, U]':
        return MenuConfig(
            handle_input,
            name,
        )

    def __init__(
            self,
            handle_input: Callable[[PromptUpdate[U]], NS[InputState[MenuState[S, ML], U], MenuAction]],
            name: str,
    ) -> None:
        self.handle_input = handle_input
        self.name = name


class Menu(Generic[S, ML, U], Dat['Menu[S, ML, U]']):

    @staticmethod
    def cons(
            config: MenuConfig[S, ML, U],
            state: MenuState[S, ML],
    ) -> 'Menu':
        return Menu(
            config,
            state,
        )

    def __init__(self, config: MenuConfig[S, ML, U], state: MenuState[S, ML]) -> None:
        self.config = config
        self.state = state


class Menus(Dat['Menus']):

    @staticmethod
    def cons(
            stack: List[NS[Any, Prog[None]]]=Nil,
    ) -> 'Menus':
        return Menus(stack)

    def __init__(self, stack: List[NS[Any, Prog[None]]]) -> None:
        self.stack = stack


__all__ = ('MenuConfig', 'MenuLine', 'MenuState', 'Menu', 'MenuContent', 'MenuAction', 'MenuQuit', 'MenuPrompt',
           'MenuUpdateLines', 'MenuUnit', 'MenuUpdateCursor', 'visible_lines', 'selected_lines', 'MenuPush', 'MenuPop',
           'Menus', 'MenuStackAction', 'MenuStackQuit', 'MenuStackPush', 'MenuStackPop',)
