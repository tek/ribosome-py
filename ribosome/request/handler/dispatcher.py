import abc
from typing import Callable, Generic, Any, TypeVar

from amino import List, Nil, Boolean, Map
from amino.util.string import snake_case
from amino.algebra import Algebra

from ribosome.logging import Logging
from ribosome.trans.handler import TransF
from ribosome.request.args import ParamsSpec

B = TypeVar('B')
D = TypeVar('D')


class RequestDispatcher(Algebra, Logging, base=True):

    @abc.abstractproperty
    def args(self) -> List[Any]:
        ...

    @abc.abstractproperty
    def name(self) -> str:
        ...

    @abc.abstractproperty
    def params_spec(self) -> Map[str, Any]:
        ...

    @property
    def allow_sync(self) -> Boolean:
        return Boolean.isinstance(self, SyncRequestDispatcher)

    @property
    def rpc_options(self) -> Map[str, Any]:
        return Map(nargs=self.params_spec.nargs.for_vim)


class SyncRequestDispatcher(RequestDispatcher):
    pass


class AsyncRequestDispatcher(RequestDispatcher):
    pass


class TransDispatcher(Generic[B], SyncRequestDispatcher):

    def __init__(self, handler: TransF[B]) -> None:
        self.handler = handler

    @property
    def args(self) -> List[Any]:
        return Nil

    def _arg_desc(self) -> List[str]:
        return List(self.name)

    @property
    def name(self) -> str:
        return self.handler.name

    @property
    def params_spec(self) -> ParamsSpec:
        return self.handler.params_spec


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

    @property
    def params_spec(self) -> ParamsSpec:
        return ParamsSpec.from_function(self.fun)


__all__ = ('RequestDispatcher', 'SyncRequestDispatcher', 'AsyncRequestDispatcher', 'TransDispatcher',
           'FunctionDispatcher')
