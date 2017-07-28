import functools
from typing import Callable, TypeVar, Any
from asyncio import iscoroutinefunction

from amino.tc.optional import Optional
from amino import Maybe, may, Either, Just, Left, I, List, _
from amino.task import TaskException

from ribosome.machine.message_base import (message, _message_attr,
                                           _machine_attr, Message,
                                           default_prio, _prio_attr,
                                           fallback_prio, override_prio)

from ribosome.record import (Record, any_field, list_field, field, bool_field,
                             optional_field)
from ribosome.logging import Logging

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


Error = message('Error', 'message')
Warning = message('Warning', 'message')
Debug = message('Debug', 'message')
Coroutine = message('Coroutine', 'coro')


def _to_error(data):
    return (
        data if isinstance(data, Message)
        else Error(data.message) if isinstance(data, Fatal)
        else Debug(data.message) if isinstance(data, NothingToDo)
        else Error(data) if isinstance(data, Exception)
        else Debug(str(data))
    )


def _recover_error(handler: 'Handler', result: Any) -> Maybe[Any]:
    if not Optional.exists(type(result)):
        err = 'in {}: result has no Optional: {}'
        return Just(Error(err.format(handler, result)))
    elif isinstance(result, Either):
        return Just(result.right_or_map(_to_error))
    else:
        return result


def _task_result(result):
    return result.cata(Left, I)


class Handler(Logging):

    def __init__(self, machine, name, message, fun, prio):
        self.machine = machine
        self.name = name
        self.message = message
        self.fun = fun
        self.prio = prio

    @staticmethod
    def create(machine, name, fun):
        tpe = CoroHandler if iscoroutinefunction(fun) else Handler
        msg = getattr(fun, _message_attr)
        prio = getattr(fun, _prio_attr, default_prio)
        return tpe(machine, name, msg, fun, prio)

    def run(self, data, msg) -> Maybe[Any]:
        result = self.fun(self.machine, data, msg)
        return _recover_error(self, result)

    def __str__(self):
        return '{}({}, {}, {})'.format(self.__class__.__name__, self.name,
                                       self.message, self.fun)


class WrappedHandler:

    def __init__(self, machine, name, message, tpe, fun, prio):
        self.machine = machine
        self.name = name
        self.message = message
        self.tpe = tpe
        self.fun = fun
        self.prio = prio

    @staticmethod
    def create(machine, name, tpe, fun):
        msg = getattr(fun, _message_attr)
        prio = getattr(fun, _prio_attr, default_prio)
        return WrappedHandler(machine, name, msg, tpe, fun, prio)

    def run(self, data, msg):
        return _recover_error(self, self.fun(self.tpe(self.machine, data, msg)))


class CoroHandler(Handler):

    def run(self, data, msg):
        return Maybe(Coroutine(self.fun(data, msg)))


class TransitionResult(Record):
    data = any_field()
    resend = list_field()
    handled = bool_field(True)
    failure = bool_field(False)
    error = optional_field()

    @staticmethod
    def empty(data, **kw):
        return StrictTransitionResult(data=data, **kw)

    @staticmethod
    def failed(data, error, **kw):
        return TransitionResult.unhandled(data, failure=True,
                                          error=Just(error), **kw)

    @staticmethod
    def unhandled(data, **kw):
        return StrictTransitionResult(data=data, handled=False, **kw)

    @property
    def _str_extra(self):
        return List(self.handled) + self.error.to_list + self.resend

    def fold(self, f):
        return self

    async def await_coro(self, callback):
        return self

    def accum(self, other: 'TransitionResult'):
        if isinstance(other, CoroTransitionResult):
            return self.accum(StrictTransitionResult(
                data=other.data, pub=other.pub,
                handled=other.handled or self.handled
            ))
        else:
            return other.set(
                pub=self.pub + other.pub,
                handled=other.handled or self.handled
            )

    @property
    def error_message(self):
        def format(err):
            return str(err.cause if isinstance(err, TaskException) else err)
        return self.error / format | 'unknown error'


class StrictTransitionResult(TransitionResult):
    pub = list_field()

    def fold(self, f):
        return self.resend.fold_left(self)(f)

    @property
    def _str_extra(self) -> List[Any]:
        return super()._str_extra + self.pub


class CoroTransitionResult(TransitionResult, Logging):
    coro = field(Coroutine)

    async def await_coro(self, callback):
        value = await self.coro.coro
        result = callback(_recover_error(self, value))
        if result.resend:
            msg = 'Cannot resend {} from coro {}, use .pub on messages'
            self.log.warn(msg.format(result.resend, self.coro))
        return result

    @property
    def pub(self):
        return [self.coro]


def handle(msg: type, prio=default_prio):
    def add_handler(func: Callable[..., Maybe[A]]):
        setattr(func, _machine_attr, True)
        setattr(func, _message_attr, msg)
        setattr(func, _prio_attr, prio)
        return func
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

__all__ = ('Handler', 'CoroHandler', 'TransitionResult',
           'StrictTransitionResult', 'CoroTransitionResult', 'handle',
           'may_handle', 'either_msg', 'either_handle', 'MachineError',
           'TransitionFailed')
