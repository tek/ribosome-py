from typing import TypeVar, Callable, Generic, Any  # type: ignore
from collections import namedtuple  # type: ignore
import abc
import inspect

import tryp
from trypnv.logging import Logging

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
        return Handler(name, getattr(fun, Machine.message_attr), fun)


class Machine(Generic[A], Logging):
    machine_attr = '_machine'
    message_attr = '_message'

    def __init__(self, name: str) -> None:
        self.name = name
        handlers = inspect.getmembers(self,
                                      lambda a: hasattr(a, self.machine_attr))
        handler_map = List.wrap(handlers)\
            .smap(Handler.create)\
            .map(lambda a: (a.message, a))
        self._message_handlers = Map(handler_map)
        self._default_handler = Handler('unhandled', None, self.unhandled)

    def process(self, data: A, msg):
        handler = self._message_handlers\
            .get(type(msg))\
            .get_or_else(lambda: self._default_handler)
        try:
            new_data = handler.fun(data, msg)
            return new_data\
                .flat_map(lambda a: Maybe.typed(a, tuple))\
                .smap(self.process)\
                .or_else(new_data)\
                .get_or_else(data)
        except Exception as e:
            errmsg = 'transition "{}" failed for {} in {}: {}'
            self.log.error(errmsg.format(handler.name, msg, self.name, e))
            if tryp.development:
                raise e
            return Just(data)

    def unhandled(self, data: A, msg: Message):
        return Maybe(data)


def handle(msg: type):
    def add_handler(func: Callable[[A, Any], Maybe[A]]):
        setattr(func, Machine.machine_attr, True)
        setattr(func, Machine.message_attr, msg)
        return func
    return add_handler


def may_handle(msg: type):
    def may_wrap(func: Callable[[A, Any], Maybe[A]]):
        return handle(msg)(may(func))
    return may_wrap


B = TypeVar('B')


class StateMachine(Machine, metaclass=abc.ABCMeta):

    def __init__(self, name: str) -> None:
        self.restart()
        Machine.__init__(self, name)

    @abc.abstractmethod
    def init(self) -> A:
        ...

    def restart(self):
        self._data = self.init()

    def send(self, msg: Message):
        self._data = self.process(self._data, msg)

__all__ = ['Machine', 'Message', 'StateMachine']
