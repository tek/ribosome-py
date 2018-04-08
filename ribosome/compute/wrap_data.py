from typing import Callable, TypeVar, Generic

from amino import Dat

R = TypeVar('R')
S = TypeVar('S')


class ProgWrappers(Generic[R, S], Dat['TransWrappers[R, S]']):

    def __init__(self, get: Callable[[R], S], put: Callable[[R, S], R]) -> None:
        self.get = get
        self.put = put


__all__ = ('TransWrappers',)
