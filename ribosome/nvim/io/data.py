import abc
from typing import Generic, TypeVar, Tuple
from traceback import FrameSummary

from amino import ADT, Either, Right, Left, Dat, Nil
from amino.util.trace import cframe
from amino.state import State

from ribosome.nvim.io.trace import NvimIOException

A = TypeVar('A')
B = TypeVar('B')


class NResult(Generic[A], ADT['NResult[A]']):

    @abc.abstractproperty
    def to_either(self) -> Either[Exception, A]:
        ...


class NSuccess(Generic[A], NResult[A]):

    def __init__(self, value: A) -> None:
        self.value = value

    @property
    def to_either(self) -> Either[Exception, A]:
        return Right(self.value)


class NError(Generic[A], NResult[A]):

    def __init__(self, error: str) -> None:
        self.error = error

    @property
    def to_either(self) -> Either[Exception, A]:
        return Left(Exception(self.error))


class NFatal(Generic[A], NResult[A]):

    def __init__(self, exception: Exception) -> None:
        self.exception = exception

    @property
    def to_either(self) -> Either[Exception, A]:
        return Left(self.exception)


class Thunk(Generic[A, B], Dat['Thunk[A, B]']):

    @staticmethod
    def cons(thunk: State[A, B], frame: FrameSummary=None) -> 'Thunk[A, B]':
        return Thunk(thunk, frame or cframe())

    def __init__(self, thunk: State[A, B], frame: FrameSummary) -> None:
        self.thunk = thunk
        self.frame = frame


def eval_thunk(resource: A, thunk: Thunk[A, B]) -> Tuple[A, B]:
    try:
        return thunk.thunk.run(resource).value
    except NvimIOException as e:
        raise e
    except Exception as e:
        raise NvimIOException('', Nil, e, thunk.frame)


__all__ = ('NResult', 'NSuccess', 'NError', 'NFatal', 'Thunk', 'eval_thunk')
