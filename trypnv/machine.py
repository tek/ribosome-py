from typing import (TypeVar, Callable, Generic, Any, Tuple, Sequence
                    )  # type: ignore
from collections import namedtuple  # type: ignore
import abc
import inspect
import threading
import asyncio
import concurrent.futures
import importlib
from contextlib import contextmanager

from toolz.itertoolz import cons  # type: ignore

from fn import _  # type: ignore

import tryp
import trypnv
from trypnv.logging import Logging

from tryp import Maybe, List, Map, may, Empty, curried


class Message(object):

    def __str__(self):
        return 'Message({})'.format(self.__class__.__name__)

    def __repr__(self):
        return str(self)

    @property
    def pub(self):
        return Publish(self)


def message(name, *fields):
    return type.__new__(type, name, (Message, namedtuple(name, fields)), {})


class Publish(Message):

    def __init__(self, message: Message) -> None:
        self.message = message

    def __str__(self):
        return 'Publish({})'.format(str(self.message))


class Nop(Message):
    pass


class Quit(Message):
    pass


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


class Callback(Message):

    def __init__(self, func: Callable[[Data], Any]):
        self.func = func


class MachineError(RuntimeError):
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

    def process(self, data: Data, msg) -> Tuple[Data, List[Publish]]:
        handler = self._message_handlers\
            .get(type(msg))\
            .get_or_else(lambda: self._default_handler)
        return self._execute_transition(handler, data, msg)\
            .map(self._process_result(data))\
            .smap(self._resend)\
            .get_or_else((data, List()))

    def _execute_transition(self, handler, data, msg):
        try:
            result = handler.fun(data, msg)
            if not isinstance(result, Maybe):
                raise MachineError('result is not Maybe: {}'.format(result))
        except Exception as e:
            import traceback
            err = 'transition "{}" failed for {} in {}'
            self.log.exception(err.format(handler.name, msg, self.name))
            if tryp.development:
                raise e
            result = Empty()
        return result

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
            e2, p2 = self.process(e, m)
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


class StateMachine(threading.Thread, Machine, metaclass=abc.ABCMeta):

    def __init__(self, name: str, sub: List[Machine]=List()) -> None:
        threading.Thread.__init__(self)
        self.done = None
        self._loop = asyncio.new_event_loop()  # type: ignore
        self._messages = asyncio.Queue(loop=self._loop)
        self.data = self.init()
        self.sub = sub
        Machine.__init__(self, name)

    @abc.abstractmethod
    def init(self) -> Data:
        ...

    def run(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self.main())

    def stop(self):
        if self.done is not None:
            self.send(Quit())
            self.done.result(10)

    async def main(self):
        self.done = concurrent.futures.Future()
        try:
            while not self.done.done():
                msg = await self._messages.get()
                for pub in self._send(msg):
                    await self._messages.put(pub)
                self._messages.task_done()
        except Exception as e:
            self.log.error('error while running state machine: {}'.format(e))

    def send(self, msg: Message):
        status = asyncio.run_coroutine_threadsafe(
            self._messages.put(msg), self._loop)
        if not trypnv.in_vim:
            status.result(10)

    def send_wait(self, msg: Message):
        self.send(msg)
        return self.await_state()

    def await_state(self):
        asyncio.run_coroutine_threadsafe(self._messages.join(), self._loop)\
            .result(5)
        return self.data

    def _send(self, msg: Message):
        self.data, pub = self.process(self.data, msg)
        return pub.map(_.message)

    @may_handle(Nop)
    def _nop(self, data: Data, msg: Quit):
        pass

    @may_handle(Quit)
    def _quit(self, data: Data, msg: Quit):
        self.done.set_result(True)

    @may_handle(Callback)
    def message_callback(self, data: Data, msg: Callback):
        return msg.func(data)

    @may
    def unhandled(self, data, msg):
        def send(z, s):
            d1, p1 = z
            d2, p2 = s.process(d1, msg)
            return d2, p1 + p2
        d, m = self.sub.fold_left((data, List()))(send)
        return List(*cons(d, m))

    @contextmanager
    def transient(self):
        self.start()
        self.send(Nop())
        yield self
        self.stop()


class PluginStateMachine(StateMachine):

    def __init__(self, name, plugins: List[str]):
        StateMachine.__init__(self, name)
        self.sub = plugins.flat_map(self.start_plugin)

    @may
    def start_plugin(self, path: str):
        try:
            mod = importlib.import_module(path)
        except ImportError as e:
            msg = 'invalid {} plugin module "{}": {}'
            self.log.error(msg.format(self.name, path, e))
        else:
            if hasattr(mod, 'Plugin'):
                name = path.split('.')[-1]
                return getattr(mod, 'Plugin')(name, self.vim)

    def plugin(self, name):
        return self.sub.find(_.name == name)

    def plug_command(self, plug_name: str, cmd_name: str, args: list):
        plug = self.plugin(plug_name)
        cmd = plug.flat_map(lambda a: a.command(cmd_name, List(args)))
        plug.zip(cmd).smap(self.send_plug_command)

    def send_plug_command(self, plug, msg):
        self.log.debug('sending command {} to plugin {}'.format(msg,
                                                                plug.name))
        self.data, pub = plug.process(self.data, msg)
        pub.map(_.message).foreach(self._messages.put_nowait)

__all__ = ['Machine', 'Message', 'StateMachine', 'PluginStateMachine']
