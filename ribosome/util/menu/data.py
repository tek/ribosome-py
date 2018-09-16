from typing import Callable, Generic, TypeVar
from queue import Queue

from amino import Dat

from ribosome.nvim.io.state import NS
from ribosome.util.menu.prompt.data import InputChar

A = TypeVar('A')


class MenuConfig(Generic[A], Dat['MenuConfig[A]']):

    @staticmethod
    def cons(
            initial: A,
            handle_input: Callable[[InputChar], NS[A, None]],
    ) -> 'MenuConfig[A]':
        return MenuConfig(
            initial,
            handle_input,
        )

    def __init__(self, initial: A, handle_input: Callable[[InputChar], NS[A, None]]) -> None:
        self.initial = initial
        self.handle_input = handle_input


class MenuState(Dat['MenuState']):

    @staticmethod
    def cons(
    ) -> 'MenuState':
        return MenuState(
            Queue()
        )

    def __init__(self, events: Queue) -> None:
        self.events = events


class Menu(Dat['Menu']):

    @staticmethod
    def cons(
            config: MenuConfig,
            internal: MenuState=None,
    ) -> 'Menu':
        return Menu(
            config,
            internal or MenuState.cons(),
        )

    def __init__(self, config: MenuConfig, internal: MenuState) -> None:
        self.config = config
        self.internal = internal


__all__ = ('InputChar', 'MenuConfig', 'MenuState', 'Menu',)
