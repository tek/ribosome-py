from typing import TypeVar, Callable, Generic, GenericMeta, Any  # type: ignore
from collections import namedtuple  # type: ignore
import abc
import inspect

from fn import _  # type: ignore

import trypnv
from trypnv.nvim import Log

from tryp import Maybe, Just, List, Map, may


class Message(object):

    def __str__(self):
        return 'Message({})'.format(self.__class__.__name__)


def message(name, *fields):
    return type.__new__(type, name, (Message, namedtuple(name, fields)), {})


A = TypeVar('A')


class Handler(object):

    def __init__(self, name, message, fun):
        self.name = name
        self.message = message
        self.fun = fun

    @staticmethod
    def create(name, fun):
        return Handler(name, fun._message, fun)


class MachineMeta(GenericMeta):  # type: ignore

    def __new__(mcs, name, bases, dct, **kw):
        inst = super(MachineMeta, mcs)\
            .__new__(mcs, name, bases, dct, **kw)  # type: ignore
        handlers = inspect.getmembers(inst, lambda a: hasattr(a, '_machine'))
        handler_map = List.wrap(handlers)\
            .smap(lambda a, b: Handler.create(a, b))\
            .map(lambda a: (a.message, a))
        setattr(inst, '_message_handlers', Map(handler_map))
        return inst


def handle_wrap(msg: type):
    def add_handler(func: Callable[[A, Any], Maybe[A]]):
        setattr(func, '_machine', True)
        setattr(func, '_message', msg)
        return func
    return add_handler


def handle(msg: type):
    return handle_wrap(msg)


def may_handle(msg: type):
    def may_wrap(func: Callable[[A, Any], Maybe[A]]):
        return handle_wrap(msg)(may(func))
    return may_wrap


class Machine(Generic[A], metaclass=MachineMeta):

    _message_handlers = None  # type: Map[type, Handler]

    def process(self, data: A, msg):
        handler = self._message_handlers.get(type(msg))
        try:
            name = handler.map(_.name).get_or_else('unhandled')
            if handler.isJust:
                new_data = handler._get.fun(self, data, msg)
            else:
                new_data = self.unhandled(data, msg)
            return new_data\
                .flat_map(lambda a: Maybe.typed(a, tuple))\
                .smap(self.process)\
                .or_else(new_data)\
                .get_or_else(data)
        except Exception as e:
            Log.error('transition "{}" failed for {}: {}'.format(name, msg, e))
            if trypnv.development:
                raise e
            return Just(data)

    def unhandled(self, data: A, msg: Message):
        return Maybe(data)


B = TypeVar('B')


class StateMachine(Generic[B], Machine[B], metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def init(self) -> A:
        ...

    def __init__(self):
        self.restart()

    def restart(self):
        self._data = self.init()

    def send(self, msg: Message):
        self._data = self.process(self._data, msg)

__all__ = ['Machine', 'Message', 'ProteomeComponent']
