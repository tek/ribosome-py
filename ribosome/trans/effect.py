import abc
from typing import TypeVar, Type, Generic

from amino import List
from amino.string.hues import red, green

from ribosome.logging import Logging
from ribosome.trans.step import TransStep, TransEffectError

R = TypeVar('R')
O = TypeVar('O')


class TransEffect(Generic[R], abc.ABC, Logging):

    @abc.abstractproperty
    def tpe(self) -> Type[R]:
        ...

    @abc.abstractmethod
    def extract(self, data: R, tail: List['TransEffect'], in_state: bool) -> TransStep:
        ...

    def typecheck(self, data: R) -> bool:
        return isinstance(data, self.tpe)

    def run(self, data: R, tail: List['TransEffect'], in_state: bool) -> TransStep:
        return (
            self.extract(data, tail, in_state)
            if self.typecheck(data) else
            TransEffectError(f'result {red(data)} does not have type {green(self.tpe.__qualname__)}')
        )


__all__ = ('TransEffect', 'lift', 'extract', 'TransComplete')
