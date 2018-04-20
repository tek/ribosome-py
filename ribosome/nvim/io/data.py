import abc
from typing import Generic, TypeVar, Tuple, Callable
from traceback import FrameSummary

from amino import ADT, Either, Right, Left, Dat, Nil
from amino.util.trace import cframe
from amino.state import State

from ribosome.nvim.io.trace import NvimIOException

A = TypeVar('A')
B = TypeVar('B')
C = TypeVar('C')


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


class Thunk(Generic[A, B, C], Dat['Thunk[A, B, C]']):

    @staticmethod
    def cons(thunk: Callable[[C], State[A, B]], frame: FrameSummary=None) -> 'Thunk[A, B, C]':
        return Thunk(thunk, frame or cframe())

    def __init__(self, thunk: Callable[[C], State[A, B]], frame: FrameSummary) -> None:
        self.thunk = thunk
        self.frame = frame


def eval_thunk(conf: C, resource: A, thunk: Thunk[A, B, C]) -> Tuple[A, B]:
    try:
        return thunk.thunk(conf).run(resource).value
    except NvimIOException as e:
        raise e
    except Exception as e:
        raise NvimIOException('', Nil, e, thunk.frame)


__all__ = ('NResult', 'NSuccess', 'NError', 'NFatal', 'Thunk', 'eval_thunk')
