from typing import (TypeVar, Callable, Generic, Any, Tuple, Sequence
                    )  # type: ignore
from collections import namedtuple  # type: ignore
import abc
import inspect
import threading

from toolz.itertoolz import cons  # type: ignore

from fn import _  # type: ignore

import tryp
from trypnv.logging import Logging

from tryp import Maybe, List, Map, may, Empty, curried


class Message(object):

    def __str__(self):
        return 'Message({})'.format(self.__class__.__name__)

    @property
    def pub(self):
        return Publish(self)


def message(name, *fields):
    return type.__new__(type, name, (Message, namedtuple(name, fields)), {})


class Publish(Message):

    def __init__(self, message: Message) -> None:
        self.message = message


def is_seq(a):
    return isinstance(a, Sequence)


def is_message(a):
    return isinstance(a, Message)


class Handler(object):

    def __init__(self, name, message, fun):
        self.name = name
        self.message = message
        self.fun = fun

    @staticmethod
    def create(name, fun):
        return Handler(name, getattr(fun, Machine.message_attr), fun)


class Data(object):
    pass


class Machine(Logging):
    machine_attr = '_machine'
    message_attr = '_message'
    _data_type = Data

    def __init__(self, name: str) -> None:
        self.name = name
        handlers = inspect.getmembers(self,
                                      lambda a: hasattr(a, self.machine_attr))
        handler_map = List.wrap(handlers)\
            .smap(Handler.create)\
            .map(lambda a: (a.message, a))
        self._message_handlers = Map(handler_map)
        self._default_handler = Handler('unhandled', None, self.unhandled)
        self._lock = threading.RLock()

    def process(self, data: Data, msg) -> Tuple[Data, List[Publish]]:
        with self._lock:
            return self._unsafe_process(data, msg)

    def _unsafe_process(self, data: Data, msg) -> Tuple[Data, List[Publish]]:
        handler = self._message_handlers\
            .get(type(msg))\
            .get_or_else(lambda: self._default_handler)
        try:
            ret = handler.fun(data, msg)\
                .map(self._process_result(data))\
                .smap(self._resend)
        except Exception as e:
            err = 'transition "{}" failed for {} in {}: {}'
            self.log.error(err.format(handler.name, msg, self.name, e))
            if tryp.development:
                raise e
            ret = Empty()
        return ret.get_or_else((data, List()))

    @curried
    def _process_result(
            self, old_data: Data, result) -> Tuple[Data, List[Publish]]:
        if isinstance(result, self._data_type):
            return result, List()
        elif isinstance(result, Message) or not is_seq(result):
            result = List(result)
        datas, rest = List.wrap(result).split_type(self._data_type)
        msgs, rest = rest.split_type(Message)
        if rest:
            err = 'invalid transition result parts in {}: {}'
            self.log.error(err.format(self.name, rest))
        return datas.head | old_data, msgs

    def _resend(self, env, msgs: List[Message]) -> Tuple[Data, List[Publish]]:
        def sender(z, m):
            e, p = z
            e2, p2 = self._unsafe_process(e, m)
            return e2, p + p2
        pub, send = msgs.split_type(Publish)
        return send.fold_left((env, pub))(sender)

    @may
    def unhandled(self, data: Data, msg: Message):
        pass


A = TypeVar('A')


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


class StateMachine(Machine, metaclass=abc.ABCMeta):

    def __init__(self, name: str, sub: List[Machine]=List()) -> None:
        self.restart()
        self.sub = sub
        Machine.__init__(self, name)

    @abc.abstractmethod
    def init(self) -> Data:
        ...

    def restart(self):
        self._data = self.init()

    def send(self, msg: Message):
        self._data = self._send(self._data, msg)
        return self._data

    def _send(self, data: Data, msg: Message):
        d2, pub = self.process(data, msg)
        return self._publish_results(d2, pub)

    def _publish_results(self, data: Data, pub: List[Publish]):
        return pub.map(_.message).fold_left(data)(self._send)

    @may
    def unhandled(self, data, msg):
        def send(z, s):
            d1, p1 = z
            d2, p2 = s.process(d1, msg)
            return d2, p1 + p2
        d, m = self.sub.fold_left((data, List()))(send)
        return List(*cons(d, m))

__all__ = ['Machine', 'Message', 'StateMachine']
