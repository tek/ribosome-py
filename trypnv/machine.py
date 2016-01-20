from typing import (TypeVar, Callable, Generic, Any, Tuple, Sequence
                    )  # type: ignore
from collections import namedtuple  # type: ignore
import abc
import inspect
import threading
import asyncio
import concurrent.futures
import importlib
import functools
from copy import copy
import time
from contextlib import contextmanager

from toolz.itertoolz import cons  # type: ignore

from fn import F, _  # type: ignore

from pyrsistent import PRecord, field
from pyrsistent._precord import _PRecordMeta

import tryp
import trypnv
from trypnv.logging import Logging
from trypnv.cmd import StateCommand
from trypnv.data import Data

from tryp import Maybe, List, Map, may, Empty, curried, Just
from tryp.lazy import lazy
from tryp.tc.monad import Monad

from tek.tools import camelcaseify


class MessageMeta(_PRecordMeta):

    # FIXME opt_fields order is lost
    def __new__(
            cls, name, bases, namespace, fields=[], opt_fields=[],
            varargs=None, **kw
    ):
        ''' create a subclass of PRecord
        **fields** is a list of strings used as names of mandatory
        PRecord fields
        **opt_fields** is a list of (string, default) used as fields
        with initial values
        the order of the names is preserved in **_field_order**
        **_field_count_min** and **_field_count_max** are used by
        `MessageCommand`
        '''
        for fname in fields:
            namespace[fname] = field(mandatory=True)
        for fname, val in opt_fields:
            namespace[fname] = field(mandatory=True, initial=val)
        if varargs:
            namespace[varargs] = field(mandatory=True, initial=List())
        inst = super().__new__(cls, name, bases, namespace, **kw)
        inst._field_varargs = varargs
        inst._field_order = list(fields) + List(*opt_fields).map(_[0])
        inst._field_count_min = len(fields)
        inst._field_count_max = (Empty() if varargs else
                                 Just(inst._field_count_min + len(opt_fields)))
        return inst

    def __init__(cls, name, bases, namespace, **kw):
        super().__init__(name, bases, namespace)


@functools.total_ordering
class Message(PRecord, metaclass=MessageMeta):
    time = field(type=float, mandatory=True)
    prio = field(type=float, mandatory=True, initial=0.5)

    def __new__(cls, *fields, **kw):
        field_map = (
            Map({cls._field_varargs: fields}) if cls._field_varargs
            else Map(zip(cls._field_order, fields))
        )
        ext_kw = field_map ** kw + ('time', time.time())
        return super().__new__(cls, **ext_kw)

    def __init__(self, *args, **kw):
        ''' this is necessary to catch the call from pyrsistent's
        evolver that is initializing instances
        '''
        pass

    def __str__(self):
        return 'Message({})'.format(self.__class__.__name__)

    def __repr__(self):
        return str(self)

    @property
    def pub(self):
        return Publish(self)

    def __lt__(self, other):
        if isinstance(other, Message):
            if self.prio == other.prio:
                return self.time < self.time
            else:
                return self.prio < other.prio
        else:
            return True

    def at(self, prio):
        return self.set(prio=float(prio))


def message(name, *fields, **kw):
    return MessageMeta.__new__(MessageMeta, name, (Message,), {},
                               fields=fields, **kw)


class Publish(Message, fields=('message',)):

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

    def run(self, data, msg):
        return self.fun(data, msg)


class Callback(Message):

    def __init__(self, func: Callable[[Data], Any]):
        self.func = func


Error = message('Error', 'message')


class MachineError(RuntimeError):
    pass


class TransitionFailed(MachineError):
    pass


class Machine(Logging):
    machine_attr = '_machine'
    message_attr = '_message'
    _data_type = Data

    def __init__(self, name: str) -> None:
        self.name = name
        self._setup_handlers()

    def _setup_handlers(self):
        handlers = inspect.getmembers(self,
                                      lambda a: hasattr(a, self.machine_attr))
        handler_map = List.wrap(handlers)\
            .smap(Handler.create)\
            .map(lambda a: (a.message, a))
        self._message_handlers = Map(handler_map)
        self._default_handler = Handler('unhandled', None, self.unhandled)

    def process(self, data: Data, msg) -> Tuple[Data, List[Publish]]:
        handler = self._resolve_handler(msg)
        return self._execute_transition(handler, data, msg)\
            .map(self._process_result(data))\
            .smap(self._resend)\
            .get_or_else((data, List()))

    def _resolve_handler(self, msg):
        return self._message_handlers\
            .get(type(msg))\
            .get_or_else(lambda: self._default_handler)

    def _execute_transition(self, handler, data, msg):
        try:
            result = handler.run(data, msg)
            if not Monad.exists(type(result)):
                raise MachineError('result has no Monad: {}'.format(result))
        except Exception as e:
            err = 'transition "{}" failed for {} in {}'
            self.log.exception(err.format(handler.name, msg, self.name))
            if tryp.development:
                raise TransitionFailed() from e
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

    def _command_by_message_name(self, name: str):
        msg_name = camelcaseify(name)
        return self._message_handlers\
            .find_key(lambda a: a.__name__ in [name, msg_name])

    def command(self, name: str, args: list):
        return self._command_by_message_name(name)\
            .map(lambda a: StateCommand(a[0]))\
            .map(_.call('dispatch', self, args))\
            .or_else(F(self._invalid_command, name))

    def _invalid_command(self, name):
        self.log.error(
            'plugin "{}" has no command "{}"'.format(self.name, name))
        return Empty()


class Transitions(object):
    State = Map

    def __init__(self, machine: Machine, data: Data, msg: Message):
        self.machine = machine
        self.data = data
        self.msg = msg

    @property
    def name(self):
        return self.machine.name

    @property
    def log(self):
        return self.machine.log

    @lazy
    def local(self):
        if isinstance(self.data, Data):
            return self.data.sub_state(self.name, lambda: self._mk_state)
        else:
            return self._mk_state

    @property
    def _mk_state(self):
        return self.State()

    def with_local(self, new_data):
        return self.data.with_sub_state(self.name, new_data)


class WrappedHandler(object):

    def __init__(self, machine, name, message, tpe, fun):
        self.machine = machine
        self.name = name
        self.message = message
        self.tpe = tpe
        self.fun = fun

    @staticmethod
    def create(machine, name, tpe, fun):
        return WrappedHandler(machine, name,
                              getattr(fun, Machine.message_attr), tpe, fun)

    def run(self, data, msg):
        return self.fun(self.tpe(self.machine, data, msg))


class ModularMachine(Machine):
    Transitions = Transitions

    def _setup_handlers(self):
        super()._setup_handlers()
        handlers = inspect.getmembers(self.Transitions,
                                      lambda a: hasattr(a, self.machine_attr))
        handler_map = List.wrap(handlers)\
            .smap(lambda n, f: WrappedHandler.create(self, n, self.Transitions,
                                                     f))\
            .map(lambda a: (a.message, a))
        self._message_handlers = self._message_handlers ** handler_map


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
        self._messages = asyncio.PriorityQueue(loop=self._loop)
        self.data = self.init()
        self.sub = sub
        self._wait_for_message = Map()
        Machine.__init__(self, name)

    def init(self) -> Data:
        return self._data_type()

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
            self.log.exception('while running state machine')

    def send(self, msg: Message, prio=0.5):
        self.log.debug('send {}'.format(msg))
        status = asyncio.run_coroutine_threadsafe(
            self._messages.put(msg), self._loop)

    def send_wait(self, msg: Message):
        self.send(msg)
        return self.await_state()

    def await_state(self):
        asyncio.run_coroutine_threadsafe(self._messages.join(), self._loop)\
            .result(5)
        return self.data

    def _send(self, msg: Message):
        try:
            self.data, pub = self.process(self.data, msg)
        except TransitionFailed as e:
            return []
        else:
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

__all__ = ['Machine', 'Message', 'StateMachine', 'PluginStateMachine', 'Error']
