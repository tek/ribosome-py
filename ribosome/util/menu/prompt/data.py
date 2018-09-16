from typing import Generic, TypeVar, Callable
from threading import Event
from queue import Queue

from amino import ADT, Dat, List, Nil

from ribosome.nvim.io.state import NS

A = TypeVar('A')


class InputChar(ADT['InputChar']):
    pass


class PrintableChar(InputChar):

    def __init__(self, char: str) -> None:
        self.char = char


class SpecialChar(InputChar):

    def __init__(self, char: str, modifiers: List[str]) -> None:
        self.char = char
        self.modifiers = modifiers


class Input(ADT['Input']):
    pass


class NoInput(Input):
    pass


class NormalInput(Input):

    def __init__(self, char: InputChar) -> None:
        self.char = char


class InterruptInput(Input):
    pass


class PromptAction(ADT['PromptAction']):
    pass


class PromptInput(PromptAction):

    def __init__(self, char: InputChar) -> None:
        self.char = char


class PromptInterrupt(PromptAction):
    pass


class Prompt(Dat['Prompt']):

    @staticmethod
    def cons(cursor: int=0, pre: str='', post: str='') -> 'Prompt':
        return Prompt(cursor, pre, post)

    def __init__(self, cursor: int, pre: str, post: str) -> None:
        self.cursor = cursor
        self.pre = pre
        self.post = post


class InputState(Generic[A], Dat['InputState[A]']):

    @staticmethod
    def cons(
            data: A,
            keys: List[InputChar]=Nil,
            prompt: Prompt=Prompt.cons(),
            cursor: int=0,
    ) -> 'InputState':
        return InputState(
            data,
            keys,
            prompt,
            cursor,
        )

    def __init__(self, data: A, keys: List[InputChar], prompt: Prompt, cursor: int) -> None:
        self.data = data
        self.keys = keys
        self.prompt = prompt
        self.cursor = cursor


class InputResources(Generic[A], Dat['InputResources[A]']):

    @staticmethod
    def cons(
            state: InputState[A],
            update: Callable[[List[InputChar]], NS[InputState[A], bool]],
            inputs: Queue=None,
            stop: Event=None,
            interval: float=.01,
    ) -> 'InputResources[A]':
        return InputResources(
            state,
            update,
            inputs or Queue(),
            stop or Event(),
            interval,
        )

    def __init__(
            self,
            state: InputState[A],
            update: Callable[[List[InputChar]], NS[InputState[A], bool]],
            inputs: Queue,
            stop: Event,
            interval: float,
    ) -> None:
        self.state = state
        self.update = update
        self.inputs = inputs
        self.stop = stop
        self.interval = interval


__all__ = ('InputChar', 'PrintableChar', 'SpecialChar', 'Input', 'NoInput', 'NormalInput', 'InterruptInput',
           'InputChar', 'InputState', 'InputResources', 'InputChar', 'PromptAction', 'PromptInput', 'PromptInterrupt',
           'Prompt',)
