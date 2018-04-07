from typing import Callable, TypeVar, Generic

from amino import Dat

A = TypeVar('A')
B = TypeVar('B')
D = TypeVar('D')


class ProgWrappers(Generic[A, B, D], Dat['TransWrappers[A, B, D]']):

    def __init__(self, get: Callable[[D, A], B], put: Callable[[B], A]) -> None:
        self.get = get
        self.put = put


__all__ = ('TransWrappers',)
