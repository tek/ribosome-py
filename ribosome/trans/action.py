import abc
from typing import TypeVar, Generic, Any, Callable
from types import SimpleNamespace
from logging import INFO, ERROR

from amino import Either, List, Id, Maybe, Nil
from amino.state import StateT
from amino.dat import ADT, ADTMeta
from amino.tc.base import Implicits, ImplicitsMeta
from amino.tc.monad import Monad
from amino.logging import LogError
from amino.func import CallByName, call_by_name

from ribosome.trans.message_base import Sendable, Message
from ribosome.trans.handler import FreeTrans

A = TypeVar('A')
B = TypeVar('B')
D = TypeVar('D')
M = TypeVar('M', bound=Message)
R = TypeVar('R')
N = TypeVar('N')
O = TypeVar('O')
G = TypeVar('G')
I = TypeVar('I')


class TransMMeta(ADTMeta, ImplicitsMeta):

    def __new__(cls, name: str, bases: List[type], namespace: SimpleNamespace, **kw: Any) -> None:
        return super().__new__(cls, name, bases, namespace, **kw)


class TransM(Generic[A], ADT['TransM'], Implicits, implicits=True, auto=True, base=True, metaclass=TransMMeta):

    @staticmethod
    def from_maybe(fa: Maybe[A], error: CallByName) -> 'TransM[A]':
        return fa / TransM.cont | (lambda: TransM.error(error))

    @staticmethod
    def from_either(fa: Either[str, A]) -> 'TransM[A]':
        return fa.cata(TransM.error, TransM.cont)

    @staticmethod
    def cont(a: A) -> 'TransM[A]':
        return TransMCont(FreeTrans.cons(lambda: TransResult(a)))

    @staticmethod
    def pure(a: A) -> 'TransM[A]':
        return TransMPure(a)

    @staticmethod
    def error(error: CallByName) -> 'TransM[A]':
        return TransMError(call_by_name(error))


class TransMCont(Generic[A], TransM[A]):

    def __init__(self, handler: FreeTrans[A]) -> None:
        self.handler = handler


class TransMBind(Generic[A], TransM[A]):

    def __init__(self, fa: TransM[A], f: Callable[[A], TransM[B]]) -> None:
        super().__init__()
        self.fa = fa
        self.f = f


class TransMPure(Generic[A], TransM[A]):

    def __init__(self, value: A) -> None:
        self.value = value


class TransMError(Generic[A], TransM[A]):

    def __init__(self, error: str) -> None:
        self.error = error


class Monad_TransM(Monad, tpe=TransM):

    def pure(self, a: A) -> TransM[A]:
        from ribosome.trans.api import trans
        @trans.free.result()
        def pure() -> A:
            return a
        return TransMCont(pure)

    def flat_map(self, fa: TransM, f: Callable[[A], TransM[B]]) -> None:
        return TransMBind(fa, f)


class TransAction(ADT['TransAction'], base=True):

    def __init__(self, messages: List[Sendable]) -> None:
        self.messages = messages


class Transit(Generic[D], TransAction):

    def __init__(self, trans: StateT[Id, D, 'Propagate']) -> None:
        super().__init__(List())
        self.trans = trans

    def _arg_desc(self) -> List[str]:
        return List(str(self.trans))


class Propagate(TransAction):

    @staticmethod
    def one(msg: Sendable) -> TransAction:
        return Propagate(List(msg))

    @staticmethod
    def maybe(msg: Maybe[Sendable]) -> TransAction:
        return Propagate(msg.to_list)

    @staticmethod
    def from_either(res: Either[str, TransAction]) -> TransAction:
        return res.value_or(lambda a: TransFailure(a))

    def _arg_desc(self) -> List[str]:
        return self.messages / str


class TransUnit(TransAction):

    def __init__(self) -> None:
        super().__init__(Nil)

    def _arg_desc(self) -> List[str]:
        return List()


class TransResult(Generic[A], TransAction):

    def __init__(self, data: A) -> None:
        self.data = data
        super().__init__(Nil)


class TransFailure(TransAction):

    def __init__(self, message: str) -> None:
        super().__init__(List())
        self.message = message

    def _arg_desc(self) -> List[str]:
        return List(self.message)


class TransIO(Generic[I], TransAction):

    def __init__(self, io: I) -> None:
        self.io = io


class TransDo(TransAction):

    def __init__(self, action: TransM) -> None:
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


__all__ = ('TransAction', 'Transit', 'Propagate', 'TransUnit', 'TransResult', 'TransFailure', 'TransM', 'TransMCont',
           'TransMBind', 'TransMPure')
