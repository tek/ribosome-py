from typing import TypeVar, Generic, Any

from amino import Either, List, Id, Maybe, Nil
from amino.state import StateT
from amino.util.string import ToStr
from amino.algebra import AlgebraMeta
from amino.dat import ADT

from ribosome.trans.message_base import Sendable, Message
from ribosome.trans.messages import Error

D = TypeVar('D')
M = TypeVar('M', bound=Message)
R = TypeVar('R')
N = TypeVar('N')
O = TypeVar('O')
G = TypeVar('G')
I = TypeVar('I')


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
        return res.value_or(lambda a: Propagate.one(Error(a)))

    def _arg_desc(self) -> List[str]:
        return self.messages / str


class TransUnit(TransAction):

    def __init__(self) -> None:
        super().__init__(Nil)

    def _arg_desc(self) -> List[str]:
        return List()


class TransResult(TransAction):

    def __init__(self, data: Any) -> None:
        self.data = data
        super().__init__(Nil)

    def _arg_desc(self) -> List[str]:
        return List()


class TransFailure(TransAction):

    def __init__(self, message: str) -> None:
        super().__init__(List())
        self.message = message

    def _arg_desc(self) -> List[str]:
        return List(self.message)


class TransIO(Generic[I], TransAction):

    def __init__(self, io: I) -> None:
        self.io = io


class TransStep(Generic[R], ToStr, metaclass=AlgebraMeta, base=True):

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


__all__ = ('TransAction', 'Transit', 'Propagate', 'TransUnit', 'TransResult', 'TransFailure', 'TransStep', 'Strict',
           'Lift', 'TransEffectError')
