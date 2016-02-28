from typing import TypeVar, Callable, Any, Tuple, Sequence  # type: ignore
import abc
import inspect
import threading
import asyncio
import concurrent.futures
import importlib
import functools
import time
from contextlib import contextmanager
from inspect import iscoroutine, iscoroutinefunction

from fn import F, _  # type: ignore

from pyrsistent import PRecord, field
from pyrsistent._precord import _PRecordMeta

import tryp
from trypnv.logging import Logging
from trypnv.cmd import StateCommand
from trypnv.data import Data
from trypnv.record import Record, any_field, list_field

from tryp import Maybe, List, Map, may, Empty, curried, Just
from tryp.lazy import lazy
from tryp.tc.monad import Monad
from tryp.util.string import camelcaseify


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


Nop = message('Nop')
Quit = message('Quit')
Coroutine = message('Coroutine', 'coro')
PlugCommand = message('PlugCommand', 'plug', 'msg')


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
        tpe = CoroHandler if iscoroutinefunction(fun) else Handler
        return tpe(name, getattr(fun, _message_attr), fun)

    def run(self, data, msg):
        result = self.fun(data, msg)
        if not Monad.exists(type(result)):
            err = 'in {}: result has no Monad: {}'
            raise MachineError(err.format(self, result))
        return result

    def __str__(self):
        return '{}({}, {}, {})'.format(self.__class__.__name__, self.name,
                                       self.message, self.fun)


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

    async def await_coro(self, process_result):
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


class CoroTransitionResult(TransitionResult):
    coro = field(Coroutine)

    async def await_coro(self, process_result):
        result = await self.coro.coro
        return result / process_result(self.data) | self.empty(self.data)

    @property
    def pub(self):
        return [self.coro]

Callback = message('Callback', 'func')
IO = message('IO', 'perform')
Error = message('Error', 'message')


class MachineError(RuntimeError):
    pass


class TransitionFailed(MachineError):
    pass


A = TypeVar('A')

_machine_attr = '_machine'
_message_attr = '_message'


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


class Machine(Logging):
    _data_type = Data

    def __init__(self, name: str) -> None:
        self.name = name
        self._setup_handlers()

    def _setup_handlers(self):
        handlers = inspect.getmembers(self,
                                      lambda a: hasattr(a, _machine_attr))
        handler_map = List.wrap(handlers)\
            .smap(Handler.create)\
            .map(lambda a: (a.message, a))
        self._message_handlers = Map(handler_map)

    @property
    def _default_handler(self):
        return Handler('unhandled', None, self.unhandled)

    def process(self, data: Data, msg) -> TransitionResult:
        handler = self._resolve_handler(msg)
        return (
            self._execute_transition(handler, data, msg) /
            self._process_result(data) |
            TransitionResult.empty(data)
        )

    def loop_process(self, data, msg):
        sender = lambda z, m: z.accum(self.loop_process(z.data, m))
        return self.process(data, msg).fold(sender)

    def _resolve_handler(self, msg):
        return self._message_handlers\
            .get(type(msg))\
            .get_or_else(lambda: self._default_handler)

    def _execute_transition(self, handler, data, msg):
        try:
            return handler.run(data, msg)
        except Exception as e:
            return self._handle_transition_error(handler, msg, e)

    def _handle_transition_error(self, handler, msg, e):
        err = 'transition "{}" failed for {} in {}'
        self.log.exception(err.format(handler.name, msg, self.name))
        if tryp.development:
            raise TransitionFailed() from e
        return Empty()

    @curried
    def _process_result(self, old_data: Data, result) -> TransitionResult:
        if isinstance(result, Coroutine):
            return CoroTransitionResult(data=old_data, coro=result)
        elif isinstance(result, TransitionResult):
            return result
        elif isinstance(result, self._data_type):
            return TransitionResult.empty(result)
        elif isinstance(result, Message) or not is_seq(result):
            result = List(result)
        datas, rest = List.wrap(result).split_type(self._data_type)
        strict, rest = rest.split_type(Message)
        coro, rest = rest.split(iscoroutine)
        msgs = strict + coro.map(Coroutine).map(_.pub)
        if rest:
            tpl = 'invalid transition result parts in {}: {}'
            msg = tpl.format(self.name, rest)
            if tryp.development:
                raise MachineError(msg)
            else:
                self.log.error(msg)
        new_data = datas.head | old_data
        return self._create_result(new_data, msgs)

    def _create_result(self, data, msgs):
        pub, resend = msgs.split_type(Publish)
        pub_msgs = pub.map(_.message)
        return StrictTransitionResult(data=data, pub=pub_msgs, resend=resend)

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

    @may_handle(IO)
    def message_callback(self, data: Data, msg: IO):
        msg.perform()


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
                              getattr(fun, _message_attr), tpe, fun)

    def run(self, data, msg):
        return self.fun(self.tpe(self.machine, data, msg))


class ModularMachine(Machine):
    Transitions = Transitions

    def _setup_handlers(self):
        super()._setup_handlers()
        handlers = inspect.getmembers(self.Transitions,
                                      lambda a: hasattr(a, _machine_attr))
        handler_map = List.wrap(handlers)\
            .smap(lambda n, f: WrappedHandler.create(self, n, self.Transitions,
                                                     f))\
            .map(lambda a: (a.message, a))
        self._message_handlers = self._message_handlers ** handler_map


class StateMachine(threading.Thread, Machine, metaclass=abc.ABCMeta):

    def __init__(self, name: str, sub: List[Machine]=List()) -> None:
        threading.Thread.__init__(self)
        self.done = None
        self.data = None
        self._messages = None
        self.running = concurrent.futures.Future()
        self.sub = sub
        Machine.__init__(self, name)

    def init(self) -> Data:
        return self._data_type()

    def run(self):
        self._loop = asyncio.new_event_loop()  # type: ignore
        self._messages = asyncio.PriorityQueue(loop=self._loop)
        asyncio.set_event_loop(self._loop)
        self.done = concurrent.futures.Future()
        self.running.set_result(True)
        try:
            self._loop.run_until_complete(self._main(self.init()))
        except Exception:
            self.log.exception('while running state machine')
        self.running = concurrent.futures.Future()

    def wait_for_running(self):
        self.running.result(3)

    def start_wait(self):
        self.start()
        self.wait_for_running()

    def stop(self):
        if self.done is not None:
            self.send(Quit())
            self.done.result(10)
            try:
                self._loop.close()
            except Exception as e:
                self.log.error(e)

    def _publish(self, msg):
        return self._messages.put(msg)

    def send(self, msg: Message, prio=0.5):
        self.log.debug('send {}'.format(msg))
        if self._messages is not None:
            return asyncio.run_coroutine_threadsafe(self._messages.put(msg),
                                                    self._loop)

    def send_sync(self, msg: Message):
        self.send(msg)
        return self.await_state()

    send_wait = send_sync

    def await_state(self):
        asyncio.run_coroutine_threadsafe(self.join(), self._loop)\
            .result(2)
        return self.data

    def _send(self, data, msg: Message):
        return (
            Maybe.from_call(
                self.loop_process, data, msg, exc=TransitionFailed) |
            TransitionResult.empty(data)
        )

    @may_handle(Nop)
    def _nop(self, data: Data, msg: Nop):
        pass

    @may_handle(Quit)
    def _quit(self, data: Data, msg: Quit):
        self.done.set_result(True)

    @may_handle(Callback)
    def message_callback(self, data: Data, msg: Callback):
        return msg.func(data)

    @may_handle(Coroutine)
    def _couroutine(self, data: Data, msg: Coroutine):
        return msg

    def unhandled(self, data, msg):
        return self._fold_sub(data, msg)

    @may
    def _fold_sub(self, data, msg):
        ''' send **msg** to all sub-machines, passing the transformed
        data from each machine to the next and accumulating published
        messages.
        '''
        send = lambda z, s: z.accum(s.loop_process(z.data, msg))
        return self.sub.fold_left(TransitionResult.empty(data))(send)

    @contextmanager
    def transient(self):
        self.start()
        self.wait_for_running()
        self.send(Nop())
        yield self
        self.stop()

    async def _main(self, data):
        self.data = data
        while not self.done.done():
            self.data = data = await self._process_one_message(data)

    async def _process_one_message(self, data):
        msg = await self._messages.get()
        sent = self._send(data, msg)
        result = await sent.await_coro(self._process_result)
        for pub in result.pub:
            await self._publish(pub)
        self._messages.task_done()
        return result.data

    async def join(self):
        await self._messages.join()


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

    def plug_command(self, plug_name: str, cmd_name: str, args: list=[],
                     sync=False):
        sender = self.send_sync if sync else self.send
        plug = self.plugin(plug_name)
        cmd = plug.flat_map(lambda a: a.command(cmd_name, List(args)))
        plug.map2(cmd, PlugCommand) % sender

    def plug_command_sync(self, *a, **kw):
        return self.plug_command(*a, sync=True, **kw)

    @may_handle(PlugCommand)
    def _plug_command(self, data, msg):
        self.log.debug(
            'sending command {} to plugin {}'.format(msg.msg, msg.plug.name))
        return msg.plug.process(data, msg.msg)

__all__ = ('Machine', 'Message', 'StateMachine', 'PluginStateMachine', 'Error')
