from typing import Generic, TypeVar, Callable
from threading import Event
from queue import Queue

from amino import ADT, Dat, List, Nil, Maybe

from ribosome.nvim.io.state import NS
from ribosome.compute.prog import Prog

A = TypeVar('A')
B = TypeVar('B')


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


class PromptInputAction(Generic[A], ADT['PromptInputAction[A]']):
    pass


class PromptInit(PromptInputAction[A]):
    pass


class PromptInput(PromptInputAction[A]):

    def __init__(self, char: InputChar) -> None:
        self.char = char


class PromptInterrupt(PromptInputAction[A]):
    pass


class PromptConsumerInput(PromptInputAction[A]):

    def __init__(self, data: A) -> None:
        self.data = data


class PromptUpdate(Generic[A], ADT['PromptUpdate[A]']):
    pass


class PromptUpdateInit(PromptUpdate[A]):
    pass


class PromptUpdateChar(PromptUpdate[A]):

    def __init__(self, char: InputChar) -> None:
        self.char = char


class PromptUpdateConsumer(PromptUpdate[A]):

    def __init__(self, data: A) -> None:
        self.data = data


class PromptConsumerUpdate(Generic[A], ADT['PromptConsumerUpdate[A]']):
    pass


class PromptConsumerInit(PromptConsumerUpdate[A]):
    pass


class PromptConsumerUnhandled(PromptConsumerUpdate[A]):

    def __init__(self, char: InputChar) -> None:
        self.char = char


class PromptConsumerChanged(PromptConsumerUpdate[A]):
    pass


class PromptConsumerLocal(PromptConsumerUpdate[A]):

    def __init__(self, data: A) -> None:
        self.data = data


class Prompt(Dat['Prompt']):

    @staticmethod
    def cons(cursor: int=0, pre: str='', post: str='') -> 'Prompt':
        return Prompt(cursor, pre, post)

    def __init__(self, cursor: int, pre: str, post: str) -> None:
        self.cursor = cursor
        self.pre = pre
        self.post = post

    @property
    def line(self) -> str:
        return self.pre + self.post


class PromptState(ADT['PromptState']):
    pass


class PromptEcho(PromptState):
    pass


class PromptPassthrough(PromptState):
    pass


class PromptAction(ADT['PromptAction']):
    pass


class PromptStateTrans(PromptAction):

    def __init__(self, state: PromptState) -> None:
        self.state = state


class PromptQuit(PromptAction):
    pass


class PromptUnit(PromptAction):
    pass


class InputState(Generic[A, B], Dat['InputState[A, B]']):

    @staticmethod
    def cons(
            data: A,
            actions: List[PromptUpdate[B]]=Nil,
            prompt: Prompt=Prompt.cons(),
            cursor: int=0,
            state: PromptState=PromptEcho(),
    ) -> 'InputState':
        return InputState(
            data,
            actions,
            prompt,
            cursor,
            state,
        )

    def __init__(
            self,
            data: A,
            actions: List[PromptUpdate[B]],
            prompt: Prompt,
            cursor: int,
            state: PromptState,
    ) -> None:
        self.data = data
        self.actions = actions
        self.prompt = prompt
        self.cursor = cursor
        self.state = state


ProcessPrompt = Callable[[PromptUpdate[B]], NS[InputState[A, B], PromptAction]]
PromptConsumer = Callable[[PromptConsumerUpdate[B]], NS[InputState[A, B], PromptAction]]


class InputResources(Generic[A, B], Dat['InputResources[A, B]']):

    @staticmethod
    def cons(
            state: InputState[A, B],
            update: Callable[[PromptUpdate[B]], NS[InputState[A, B], None]],
            inputs: Queue=None,
            stop: Event=None,
            interval: float=.01,
    ) -> 'InputResources[A, B]':
        return InputResources(
            state,
            update,
            inputs or Queue(),
            stop or Event(),
            interval,
        )

    def __init__(
            self,
            state: InputState[A, B],
            update: Callable[[PromptUpdate[B]], NS[InputState[A, B], None]],
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
           'InputState', 'InputResources', 'InputChar', 'PromptInputAction', 'PromptInput', 'PromptInterrupt',
           'Prompt', 'PromptState', 'PromptEcho', 'PromptQuit', 'PromptPassthrough', 'PromptUnit', 'PromptAction',
           'PromptStateTrans', 'PromptUnit', 'PromptQuitWith', 'PromptConsumerInput', 'PromptUpdate',
           'PromptUpdateChar', 'PromptUpdateConsumer', 'PromptInit', 'PromptUpdateInit', 'PromptConsumerUpdate',
           'PromptConsumerInit', 'PromptConsumerUnhandled', 'PromptConsumerChanged', 'PromptConsumerLocal',
           'PromptConsumer',)
