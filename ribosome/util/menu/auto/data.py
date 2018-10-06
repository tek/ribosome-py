from typing import TypeVar, Callable, Generic, Any

from amino import ADT, List, Dat, Map

from ribosome.util.menu.data import MenuAction, MenuState, MenuLine
from ribosome.util.menu.prompt.data import InputState, PromptConsumerUpdate
from ribosome.nvim.io.state import NS

S = TypeVar('S')
ML = TypeVar('ML')
U = TypeVar('U')
MenuS = NS[InputState[MenuState[S, ML, U], U], MenuAction]


class AutoUpdate(Generic[U, ML], ADT['AutoUpdate[U, ML]']):
    pass


class AutoUpdateRefresh(AutoUpdate[U, ML]):

    def __init__(self, lines: List[MenuLine[ML]]) -> None:
        self.lines = lines


class AutoUpdateConsumer(AutoUpdate[U, ML]):

    def __init__(self, data: U) -> None:
        self.data = data


class AutoState(Generic[S, ML, U], Dat['AutoState[S, ML, U]']):

    def __init__(
            self,
            consumer: Callable[[PromptConsumerUpdate[AutoUpdate[U, ML]]],
                               NS[InputState[MenuState[Any, ML, U], AutoUpdate[U, ML]], MenuAction]],
            state: S,
            mappings: Map[str, Callable[[], MenuS[S, AutoUpdate[U, ML], ML]]],
    ) -> None:
        self.consumer = consumer
        self.state = state
        self.mappings = mappings


AutoS = MenuS[AutoState[S, ML, U], ML, AutoUpdate[U, ML]]

__all__ = ('S', 'ML', 'U', 'MenuS', 'AutoUpdate', 'AutoUpdateRefresh', 'AutoUpdateConsumer', 'AutoState', 'AutoS',)
