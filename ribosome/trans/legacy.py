import abc
from typing import Callable, TypeVar, Any, Generic, Type, Tuple, Union, Generator
from asyncio import iscoroutinefunction

from amino.tc.optional import Optional
from amino import Maybe, Either, Just, Left, I, List, Nothing, Id, Nil
from amino.state import StateT
from amino.util.string import ToStr
from amino.dat import Dat, DatMeta
from amino.do import do

from ribosome.trans.message_base import _message_attr, Message, default_prio, _prio_attr, _dyn_attr

from ribosome.logging import Logging
from ribosome.trans.messages import Error, Debug, Coroutine

A = TypeVar('A')


class Failure:

    def __init__(self, message: str) -> None:
        self.message = message

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, self.message)


class Fatal(Failure):
    pass


class NothingToDo(Failure):
    pass


def _to_error(data):
    return (
        data if isinstance(data, Message)
        else Error(data.message) if isinstance(data, Fatal)
        else Debug(data.message) if isinstance(data, NothingToDo)
        else Error(data) if isinstance(data, Exception)
        else Debug(str(data))
    )


def _recover_error(handler: Any, result: Any) -> Maybe[Any]:
    if not Optional.exists(type(result)):
        err = 'in {}: result has no Optional: {}'
        return Just(Error(err.format(handler, result)))
    elif isinstance(result, Either):
        return Just(result.right_or_map(_to_error))
    else:
        return result


def _io_result(result):
    return result.cata(Left, I)

D = TypeVar('D')
M = TypeVar('M', bound=Message)
R = TypeVar('R')
DynResult = Union[Message, List[Message]]
DynTrans = Union[DynResult, Maybe[DynResult], Either[str, DynResult], StateT[Id, D, DynResult]]


class Handler:
    pass


class LegacyHandler(Generic[M, D, R], Handler, Logging, ToStr):

    def __init__(self, name: str, fun: Callable[[D, M], R], message: Type[M], prio: float, dyn: bool) -> None:
        self.name = name
        self.message = message
        self.fun = fun
        self.prio = prio
        self.dyn = dyn

    @staticmethod
    def attrs(fun: Callable) -> Tuple[str, Type[M], float, bool]:
        name = fun.__name__
        msg = getattr(fun, _message_attr, None)
        prio = getattr(fun, _prio_attr, default_prio)
        dyn = getattr(fun, _dyn_attr, False)
        return name, msg, prio, dyn

    @staticmethod
    def create(fun: Callable[[D, M], R]) -> 'LegacyHandler[M, D, R]':
        name, msg, prio, dyn = LegacyHandler.attrs(fun)
        tpe = CoroHandler if iscoroutinefunction(fun) else DynHandler  # if dyn else TransHandler
        return tpe(name, fun, msg, prio, dyn)

    @abc.abstractmethod
    def execute(self, data: D, msg: M) -> R:
        ...

    @abc.abstractmethod
    def run(self, data: D, msg: M) -> R:
        ...

    def _arg_desc(self) -> List[str]:
        return List(self.name, str(self.message), str(self.fun))


class DynHandler(Generic[M, D], LegacyHandler[M, D, DynTrans]):

    def run(self, data, msg) -> DynTrans:
        return _recover_error(self, self.execute(data, msg))

    def execute(self, data, msg) -> DynTrans:
        return self.fun(data, msg)


class CoroHandler(LegacyHandler):

    def run(self, data, msg) -> Maybe[Coroutine]:
        return Maybe(Coroutine(self.fun(data, msg)))

    def execute(self, data, msg) -> Maybe[Coroutine]:
        ...


class CoroExecutionHandler(DynHandler):
    pass


class TransitionLogMeta(DatMeta):

    @property
    def empty(self) -> 'TransitionLog':
        return TransitionLog(Nil, Nil)


class TransitionLog(Dat['TransitionLog'], metaclass=TransitionLogMeta):

    def __init__(self, message_log: List[Message], message_resend: List[Message]) -> None:
        self.message_log = message_log
        self.message_resend = message_resend

    def log(self, m: Message) -> 'TransitionLog':
        return self.append1.message_log(m)

    def resend(self, ms: List[Message]) -> 'TransitionLog':
        return self.append.message_resend(ms)

    @property
    def pop(self) -> Generator:
        @do(Maybe[Tuple['TransitionLog', Maybe[Message]]])
        def pop1() -> Generator:
            head, tail = yield self.message_resend.detach_head
            yield Just((self.copy(message_resend=tail).log(head), Just(head)))
        return pop1() | (self, Nothing)


class MachineError(RuntimeError):
    pass


class TransitionFailed(MachineError):
    pass

__all__ = ('LegacyHandler', 'CoroHandler', 'handle', 'may_handle', 'either_msg', 'either_handle', 'MachineError', 'TransitionFailed', 'TransitionLog')
