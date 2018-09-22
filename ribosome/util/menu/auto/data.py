from typing import TypeVar, Callable, Generic, Any

from amino import ADT, List, Dat, Map

from ribosome.util.menu.data import MenuAction, MenuState, MenuLine
from ribosome.util.menu.prompt.data import InputState, PromptUpdate
from ribosome.nvim.io.state import NS

S = TypeVar('S')
ML = TypeVar('ML')
U = TypeVar('U')
MenuS = NS[InputState[MenuState[S, ML], U], MenuAction]


class AutoUpdate(Generic[U, ML], ADT['AutoUpdate[U, ML]']):
    pass


class AutoUpdateRefresh(AutoUpdate[U, ML]):

    def __init__(self, lines: List[MenuLine[ML]]) -> None:
        self.lines = lines


class AutoUpdateConsumer(AutoUpdate[U, ML]):

    def __init__(self, data: U) -> None:
        self.data = data


class AutoState(Generic[U, ML, S], Dat['AutoState[U, ML, S]']):

    def __init__(
            self,
            process: Callable[[PromptUpdate[AutoUpdate[U, ML]]], MenuS[Any, AutoUpdate[U, ML], ML]],
            state: S,
            mappings: Map[str, Callable[[], MenuS[S, AutoUpdate[U, ML], ML]]],
    ) -> None:
        self.process = process
        self.state = state
        self.mappings = mappings


AutoS = MenuS[AutoState[U, ML, S], ML, AutoUpdate[U, ML]]

__all__ = ('S', 'ML', 'U', 'MenuS', 'AutoUpdate', 'AutoUpdateRefresh', 'AutoUpdateConsumer', 'AutoState', 'AutoS',)
