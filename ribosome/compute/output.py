from typing import Callable, TypeVar, Generic

from amino import ADT
from ribosome.nvim.io.state import NS

A = TypeVar('A')
B = TypeVar('B')
D = TypeVar('D')
P = TypeVar('P')
PIO = TypeVar('PIO')
ProgIOInterpreter = Callable[[PIO], NS[D, A]]


class ProgOutputInterpreter(Generic[A, B], ADT['ProgOutputInterpreter[A, B]']):
    pass


class ProgOutputUnit(ProgOutputInterpreter[None, None]):
    pass


class ProgOutputResult(Generic[A], ProgOutputInterpreter[A, A]):
    pass


class ProgOutputIO(Generic[PIO, A, D], ProgOutputInterpreter[PIO, A]):

    def __init__(self, interpreter: Callable[[PIO], NS[D, A]]) -> None:
        self.interpreter = interpreter


class ProgResult(Generic[A], ADT['ProgResult[A]']):
    pass


class ProgReturn(Generic[A], ProgResult[A]):

    def __init__(self, value: A) -> None:
        self.value = value


__all__ = ('ProgOutputInterpreter', 'ProgOutputUnit', 'ProgOutputResult', 'ProgOutputIO', 'ProgResult', 'ProgReturn')
