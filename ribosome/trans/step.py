from typing import Generic, TypeVar

from amino import ADT, List

R = TypeVar('R')


class TransStep(Generic[R], ADT['TransStep[R]']):

    def __init__(self, data: R) -> None:
        self.data = data

    @property
    def strict(self) -> bool:
        return isinstance(self, Strict)

    @property
    def error(self) -> bool:
        return isinstance(self, TransEffectError)

    def _arg_desc(self) -> List[str]:
        return List(str(self.data))


class Strict(Generic[R], TransStep[R]):
    pass


class Lift(Generic[R], TransStep[R]):
    pass


class TransEffectError(TransStep[str]):
    pass


__all__ = ('TransStep', 'Strict', 'Lift', 'TransEffectError')
