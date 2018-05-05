import abc

from amino import List, Maybe, Just, Nothing
from amino.dat import ADT


class Nargs(ADT['Nargs']):

    @staticmethod
    def cons(min: int, mmax: Maybe[int]) -> 'Nargs':
        def from_min() -> Nargs:
            return NargsStar() if min == 0 else NargsPlus()
        def with_max(max: int) -> Nargs:
            return (
                Just(NargsZero())
                if max == 0 else
                (
                    Just(NargsOne())
                    if min == 1 else
                    Just(NargsQM())
                )
                if max == 1 else
                Nothing
            )
        return mmax.flat_map(with_max) | from_min

    @abc.abstractproperty
    def for_vim(self) -> str:
        ...

    def _arg_desc(self) -> List[str]:
        return List()


class NargsZero(Nargs):

    @property
    def for_vim(self) -> str:
        return '0'


class NargsOne(Nargs):

    @property
    def for_vim(self) -> str:
        return '1'


class NargsStar(Nargs):

    @property
    def for_vim(self) -> str:
        return '*'


class NargsPlus(Nargs):

    @property
    def for_vim(self) -> str:
        return '+'


class NargsQM(Nargs):

    @property
    def for_vim(self) -> str:
        return '?'

__all__ = ('Nargs',)
