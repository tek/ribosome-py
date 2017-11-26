import abc
from typing import Callable, Type, Generic, Any, TypeVar

from amino import List, Nil, Boolean
from amino.util.string import snake_case
from amino.algebra import Algebra

from ribosome.logging import Logging
from ribosome.trans.handler import FreeTransHandler
from ribosome.trans.message_base import Message

B = TypeVar('B')
D = TypeVar('D')
M = TypeVar('M', bound=Message)


class RequestDispatcher(Algebra, Logging, base=True):

    @abc.abstractproperty
    def args(self) -> List[Any]:
        ...

    @abc.abstractproperty
    def name(self) -> str:
        ...

    @property
    def allow_sync(self) -> Boolean:
        return Boolean.isinstance(self, SyncRequestDispatcher)


class SyncRequestDispatcher(RequestDispatcher):
    pass


class AsyncRequestDispatcher(RequestDispatcher):
    pass


class MsgDispatcher(Generic[M], AsyncRequestDispatcher):

    def __init__(self, msg: Type[M]) -> None:
        self.msg = msg

    def _arg_desc(self) -> List[str]:
        return List(self.msg.__name__)

    @property
    def args(self) -> List[Any]:
        return List(self.msg)

    @property
    def name(self) -> str:
        return snake_case(self.msg.__name__)


class TransDispatcher(Generic[B], SyncRequestDispatcher):

    def __init__(self, handler: FreeTransHandler[D, B]) -> None:
        self.handler = handler

    @property
    def args(self) -> List[Any]:
        return Nil

    def _arg_desc(self) -> List[str]:
        return List(self.name)

    @property
    def name(self) -> str:
        return self.handler.name


class FunctionDispatcher(SyncRequestDispatcher):

    def __init__(self, fun: Callable) -> None:
        self.fun = fun

    def _arg_desc(self) -> List[str]:
        return List()

    @property
    def args(self) -> List[Any]:
        return List()

    @property
    def name(self) -> str:
        return snake_case(self.fun.__name__)


__all__ = ('RequestDispatcher', 'SyncRequestDispatcher', 'AsyncRequestDispatcher', 'MsgDispatcher', 'TransDispatcher',
           'FunctionDispatcher')
