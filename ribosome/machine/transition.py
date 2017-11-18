import abc
import functools
from typing import Callable, TypeVar, Any, Generic, Type, Tuple, Union, Generator
from asyncio import iscoroutinefunction

from amino.tc.optional import Optional
from amino import Maybe, may, Either, Just, Left, I, List, Nothing, _, __, Id, Nil
from amino.io import IOException
from amino.util.exception import format_exception
from amino.state import StateT
from amino.util.string import ToStr
from amino.dat import Dat, DatMeta
from amino.do import do

from ribosome.machine.message_base import (_message_attr, _machine_attr, Message, default_prio, _prio_attr,
                                           fallback_prio, override_prio, _dyn_attr)

from ribosome.record import Record, any_field, list_field, field, bool_field, optional_field, maybe_field
from ribosome.logging import Logging, ribo_log
from ribosome.machine.machine import Machine
from ribosome.data import Data
from ribosome.machine.transitions import Transitions
from ribosome.machine.messages import Error, Debug, Coroutine

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

D = TypeVar('D', bound=Data)
M = TypeVar('M', bound=Message)
R = TypeVar('R')
T = TypeVar('T', bound=Transitions)
Mes = TypeVar('Mes', bound=Message)
DynResult = Union[Message, List[Message]]
DynTrans = Union[DynResult, Maybe[DynResult], Either[str, DynResult], StateT[Id, Data, DynResult]]


class Handler(Generic[M, D, R], Logging, ToStr):

    def __init__(self, name: str, fun: Callable[[Machine, D, M], R], message: Type[M], prio: float, dyn: bool) -> None:
        self.name = name
        self.message = message
        self.fun = fun
        self.prio = prio
        self.dyn = dyn

    @staticmethod
    def attrs(fun: Callable) -> Tuple[str, Type[M], float, bool]:
        name = fun.__name__
        msg = getattr(fun, _message_attr)
        prio = getattr(fun, _prio_attr, default_prio)
        dyn = getattr(fun, _dyn_attr)
        return name, msg, prio, dyn

    @staticmethod
    def create(fun: Callable[[Machine, D, M], R]) -> 'Handler[M, D, R]':
        name, msg, prio, dyn = Handler.attrs(fun)
        tpe = CoroHandler if iscoroutinefunction(fun) else DynHandler  # if dyn else AlgHandler
        return tpe(name, fun, msg, prio, dyn)

    @abc.abstractmethod
    def execute(self, machine: Machine, data: D, msg: Mes) -> R:
        ...

    @abc.abstractmethod
    def run(self, machine: Machine, data: D, msg: Mes) -> R:
        ...

    def _arg_desc(self) -> List[str]:
        return List(self.name, str(self.message), str(self.fun))


class DynHandler(Generic[M, D], Handler[M, D, DynTrans]):

    def run(self, machine: Machine, data, msg) -> DynTrans:
        return _recover_error(self, self.execute(machine, data, msg))

    def execute(self, machine: Machine, data, msg) -> DynTrans:
        return self.fun(machine, data, msg)


class CoroHandler(Handler):

    def run(self, data, msg) -> Maybe[Coroutine]:
        return Maybe(Coroutine(self.fun(data, msg)))

    def execute(self, data, msg) -> Maybe[Coroutine]:
        ...


class CoroExecutionHandler(DynHandler):
    pass


# class TransitionResult(Record):
#     data = any_field()
#     resend = list_field()
#     handled = bool_field(True)
#     failure = bool_field(False)
#     error = optional_field()
#     output = maybe_field(object)

#     @staticmethod
#     def empty(data, **kw):
#         return StrictTransitionResult(data=data, **kw)

#     @staticmethod
#     def failed(data: D, error: Union[Exception, str], **kw: Any) -> 'TransitionResult':
#         return TransitionResult.unhandled(data, failure=True, error=Just(error), **kw)

#     @staticmethod
#     def unhandled(data, **kw):
#         return StrictTransitionResult(data=data, handled=False, **kw)

#     @property
#     def _str_extra(self):
#         return List(self.handled.cata('handled', 'unhandled')) + self.error.to_list + self.resend

#     def fold(self, f):
#         return self

#     def accum(self, other: 'TransitionResult'):
#         if isinstance(other, CoroTransitionResult):
#             return self.accum(StrictTransitionResult(
#                 data=other.data,
#                 pub=other.pub,
#                 handled=other.handled or self.handled,
#                 failure=other.failure or self.failure,
#                 error=other.error.o(self.error),
#             ))
#         else:
#             return other.set(
#                 pub=self.pub + other.pub,
#                 handled=other.handled or self.handled,
#                 failure=other.failure or self.failure,
#                 error=other.error.o(self.error),
#             )

#     @property
#     def error_message(self):
#         def format(err):
#             return str(err.cause if isinstance(err, IOException) else err)
#         return self.error / format | 'unknown error'

#     @property
#     def exception(self) -> Maybe[Exception]:
#         def analyze(e: Exception) -> Exception:
#             return (
#                 e.__cause__
#                 if isinstance(e, TransitionFailed) and e.__cause__ is not None else
#                 e.cause
#                 if isinstance(e, IOException) else
#                 e
#             )
#         return self.error // (lambda err: Just(analyze(err)) if isinstance(err, Exception) else Nothing)

#     @property
#     def exception_fmt(self) -> Maybe[str]:
#         return (self.exception / format_exception) / __.cons('Exception:') / _.join_lines


# class StrictTransitionResult(TransitionResult):
#     pub = list_field()

#     def fold(self, f):
#         return self.resend.fold_left(self)(f)

#     @property
#     def _str_extra(self) -> List[Any]:
#         return super()._str_extra + self.pub


# class CoroTransitionResult(TransitionResult, Logging):
#     coro = field(Coroutine)

#     @property
#     def pub(self):
#         return [self.coro]


TransitionResult = object


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


def handle(msg: type, prio=default_prio):
    def add_handler(func: Callable[..., Maybe[A]]):
        setattr(func, _machine_attr, True)
        setattr(func, _message_attr, msg)
        setattr(func, _prio_attr, prio)
        setattr(func, _dyn_attr, True)
        return Handler.create(func)
    return add_handler


def may_handle(msg: type, prio=default_prio):
    def may_wrap(func: Callable[..., Maybe[A]]):
        return handle(msg, prio=prio)(may(func))
    return may_wrap


def fallback(msg: type, prio=fallback_prio):
    return handle(msg, prio=prio)


def may_fallback(msg: type, prio=fallback_prio):
    return may_handle(msg, prio=prio)


def override(msg: type, prio=override_prio):
    return handle(msg, prio=prio)


def may_override(msg: type, prio=override_prio):
    return may_handle(msg, prio=prio)


def either_msg(e: Either):
    return e.right_or_map(Error)


def either_handle(msg: type):
    def decorator(f):
        @functools.wraps(f)
        def either_wrap(*args, **kwargs):
            return Just(either_msg(f(*args, **kwargs)))
        return handle(msg)(either_wrap)
    return decorator


class MachineError(RuntimeError):
    pass


class TransitionFailed(MachineError):
    pass

__all__ = ('Handler', 'CoroHandler', 'TransitionResult', 'StrictTransitionResult', 'CoroTransitionResult', 'handle',
           'may_handle', 'either_msg', 'either_handle', 'MachineError', 'TransitionFailed', 'TransitionLog')
