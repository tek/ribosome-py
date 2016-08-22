import functools
from typing import Callable, TypeVar, Any
from asyncio import iscoroutinefunction

from amino.tc.optional import Optional
from amino import F, Maybe, __, _, may, Either, Just

from ribosome.machine.message_base import message, _message_attr, _machine_attr

from ribosome.record import Record, any_field, list_field, field
from ribosome.logging import Logging

A = TypeVar('A')

Error = message('Error', 'message')
Coroutine = message('Coroutine', 'coro')


def _recover_error(handler, result):
    if not Optional.exists(type(result)):
        err = 'in {}: result has no Optional: {}'
        raise MachineError(err.format(handler, result))
    to_error = F(Maybe) / Error / _.pub >> __.to_either(None)
    return (
        result
        .to_either(None)
        .recover_with(to_error)
    )


class Handler:

    def __init__(self, machine, name, message, fun):
        self.machine = machine
        self.name = name
        self.message = message
        self.fun = fun

    @staticmethod
    def create(machine, name, fun):
        tpe = CoroHandler if iscoroutinefunction(fun) else Handler
        return tpe(machine, name, getattr(fun, _message_attr), fun)

    def run(self, data, msg):
        return _recover_error(self, self.fun(self.machine, data, msg))

    def __str__(self):
        return '{}({}, {}, {})'.format(self.__class__.__name__, self.name,
                                       self.message, self.fun)


class WrappedHandler:

    def __init__(self, machine, name, message, tpe, fun):
        self.machine = machine
        self.name = name
        self.message = message
        self.tpe = tpe
        self.fun = fun

    @staticmethod
    def create(machine, name, tpe, fun):
        return WrappedHandler(machine, name,
                              getattr(fun, _message_attr), tpe, fun)

    def run(self, data, msg):
        return self.fun(self.tpe(self.machine, data, msg))


class CoroHandler(Handler):

    def run(self, data, msg):
        return Maybe(Coroutine(self.fun(data, msg)))


class TransitionResult(Record):
    data = any_field()
    resend = list_field()

    @staticmethod
    def empty(data):
        return StrictTransitionResult(data=data)

    def fold(self, f):
        return self

    async def await_coro(self, callback):
        return self

    def accum(self, other: 'TransitionResult'):
        if isinstance(other, CoroTransitionResult):
            return self.accum(StrictTransitionResult(data=other.data,
                                                     pub=other.pub))
        else:
            return other.set(
                pub=self.pub + other.pub,
            )


class StrictTransitionResult(TransitionResult):
    pub = list_field()

    def fold(self, f):
        return self.resend.fold_left(self)(f)


class CoroTransitionResult(TransitionResult, Logging):
    coro = field(Coroutine)

    async def await_coro(self, callback):
        value = await self.coro.coro
        result = callback(self.data, _recover_error(self, value))
        if result.resend:
            msg = 'Cannot resend {} from coro {}, use .pub on messages'
            self.log.warn(msg.format(result.resend, self.coro))
        return result

    @property
    def pub(self):
        return [self.coro]


def handle(msg: type):
    def add_handler(func: Callable[[A, Any], Maybe[A]]):
        setattr(func, _machine_attr, True)
        setattr(func, _message_attr, msg)
        return func
    return add_handler


def may_handle(msg: type):
    def may_wrap(func: Callable[[A, Any], Maybe[A]]):
        return handle(msg)(may(func))
    return may_wrap


def either_msg(e: Either):
    return e.right_or_map(F(Error) >> _.pub)


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
