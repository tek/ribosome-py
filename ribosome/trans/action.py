import abc
from typing import TypeVar, Generic
from logging import INFO, ERROR

from amino import List, Id
from amino.state import StateT
from amino.dat import ADT
from amino.logging import LogError

from ribosome.trans.handler import Trans

A = TypeVar('A')
B = TypeVar('B')
D = TypeVar('D')
R = TypeVar('R')
N = TypeVar('N')
O = TypeVar('O')
G = TypeVar('G')
I = TypeVar('I')


class TransAction(ADT['TransAction'], base=True):
    pass


class Transit(Generic[D], TransAction):

    def __init__(self, trans: StateT[Id, D, None]) -> None:
        self.trans = trans

    def _arg_desc(self) -> List[str]:
        return List(str(self.trans))


class TransUnit(TransAction):

    def _arg_desc(self) -> List[str]:
        return List()


class TransResult(Generic[A], TransAction):

    def __init__(self, data: A) -> None:
        self.data = data


class TransFailure(TransAction):

    def __init__(self, message: str) -> None:
        self.message = message

    def _arg_desc(self) -> List[str]:
        return List(self.message)


class TransIO(Generic[I], TransAction):

    def __init__(self, io: I) -> None:
        self.io = io


class TransDo(TransAction):

    def __init__(self, action: Trans) -> None:
        self.action = action


class LogMessage(ADT['LogMessage']):

    def __init__(self, message: str) -> None:
        self.message = message

    @abc.abstractproperty
    def level(self) -> int:
        ...


class Info(LogMessage):

    @property
    def level(self) -> int:
        return INFO


class Error(LogMessage, LogError):

    def __init__(self, message: str, prefix: str='') -> None:
        super().__init__(message)
        self.prefix = prefix

    @property
    def level(self) -> int:
        return ERROR

    @property
    def full(self) -> str:
        pre = f'{self.prefix}: ' if self.prefix else ''
        return f'{pre}{self.message}'

    @property
    def short(self) -> str:
        return self.message


class TransLog(TransAction):

    def __init__(self, message: LogMessage) -> None:
        self.message = message


__all__ = ('TransAction', 'Transit', 'TransUnit', 'TransResult', 'TransFailure')
