from typing import TypeVar, Callable, Any, Sequence
import abc
import inspect
import threading
import asyncio
from concurrent import futures
import importlib
import functools
import time
from contextlib import contextmanager
from inspect import iscoroutine, iscoroutinefunction

from fn import _

from pyrsistent import PRecord
from pyrsistent._precord import _PRecordMeta

import amino
from ribosome.logging import Logging
from ribosome.cmd import StateCommand
from ribosome.data import Data
from ribosome.record import Record, any_field, list_field, field, dfield
from ribosome.nvim import NvimIO, HasNvim
from ribosome import NvimFacade

from amino import (Maybe, List, Map, may, Empty, curried, Just, __, F, Either,
                   Try)
from amino.lazy import lazy
from amino.util.string import camelcaseify
from amino.tc.optional import Optional
from amino.task import Task


def _field_namespace(fields, opt_fields, varargs):
    namespace = Map()
    for fname in fields:
        namespace[fname] = any_field()
    for fname, val in opt_fields:
        namespace[fname] = dfield(val)
    if varargs:
        namespace[varargs] = list_field()
    return namespace


def _init_field_metadata(inst):
    def set_missing(name, default):
        if not hasattr(inst, name):
            setattr(inst, name, default)
    List(
        ('_field_varargs', None),
        ('_field_order', []),
        ('_field_count_min', 0),
    ).map2(set_missing)


def _update_field_metadata(inst, fields, opt_fields, varargs):
    if varargs is not None:
        inst._field_varargs = varargs
    inst._field_order += list(fields) + List(*opt_fields).map(_[0])
    inst._field_count_min += len(fields)
    inst._field_count_max = (
        Empty() if inst._field_varargs
        else Just(inst._field_count_min + len(opt_fields)))


class MessageMeta(_PRecordMeta):

    def __new__(cls, name, bases, namespace, fields=[], opt_fields=[],
                varargs=None, skip_fields=False, **kw):
        ''' create a subclass of PRecord
        **fields** is a list of strings used as names of mandatory
        PRecord fields
        **opt_fields** is a list of (string, default) used as fields
        with initial values
        the order of the names is preserved in **_field_order**
        **varargs** is an optional field name where unmatched args are
        stored.
        **skip_fields** indicates that the current class is a base class
        (like Message). If those classes were processed here, all their
        subclasses would share the metadata, and get all fields set by
        other subclasses.
        **_field_count_min** and **_field_count_max** are used by
        `MessageCommand`
        '''
        ns = Map() if skip_fields else _field_namespace(fields, opt_fields,
                                                        varargs)
        inst = super().__new__(cls, name, bases, ns ** namespace, **kw)
        if not skip_fields:
            _init_field_metadata(inst)
            _update_field_metadata(inst, fields, opt_fields, varargs)
        return inst

    def __init__(cls, name, bases, namespace, **kw):
        super().__init__(name, bases, namespace)


@functools.total_ordering
class Message(PRecord, metaclass=MessageMeta, skip_fields=True):
    ''' Interface between vim commands and state.
    Provides a constructor that allows specification of fields via
    positional arguments.
    '''
    time = field(float)
    prio = dfield(0.5)

    def __new__(cls, *args, **kw):
        field_map = (
            Map({cls._field_varargs: args}) if cls._field_varargs
            else Map(zip(cls._field_order, args))
        )
        ext_kw = field_map ** kw + ('time', time.time())
        return super().__new__(cls, **ext_kw)

    def __init__(self, *args, **kw):
        ''' this is necessary to catch the call from pyrsistent's
        evolver that is initializing instances
        '''
        pass

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


def json_message(name, *fields, **kw):
    f = fields + ('options',)
    return message(name, *f, **kw)


class Publish(Message, fields=('message',)):

    def __str__(self):
        return 'Publish({})'.format(str(self.message))


Nop = message('Nop')
Stop = message('Stop')
Quit = message('Quit')
Done = message('Done')
Coroutine = message('Coroutine', 'coro')
PlugCommand = message('PlugCommand', 'plug', 'msg')
NvimIOTask = message('NvimIOTask', 'io')


def is_seq(a):
    return isinstance(a, Sequence)


def is_message(a):
    return isinstance(a, Message)


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


def io(f: Callable):
    return NvimIOTask(NvimIO(f))


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
        return _recover_error(self, self.fun(data, msg))

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

Callback = message('Callback', 'func')
IO = message('IO', 'perform')
Error = message('Error', 'message')
Info = message('Info', 'message')
RunTask = message('RunTask', 'task')
DataTask = message('DataTask', 'cons')


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


def either_msg(e: Either):
    return e.right_or_map(F(Error) >> _.pub)


def either_handle(msg: type):
    def decorator(f):
        @functools.wraps(f)
        def either_wrap(*args, **kwargs):
            return Just(either_msg(f(*args, **kwargs)))
        return handle(msg)(either_wrap)
    return decorator


class Machine(Logging):
    _data_type = Data

    def __init__(self, parent: 'Machine'=None, title=None) -> None:
        self.parent = Maybe(parent)
        self._title = Maybe(title)
        self._setup_handlers()

    @property
    def title(self):
        return self._title.or_else(
            List.wrap(type(self).__module__.rsplit('.')).reversed.lift(1)
        ) | 'machine'

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
        self.prepare(msg)
        handler = self._resolve_handler(msg)
        result = self._execute_transition(handler, data, msg)
        return self._dispatch_transition_result(data, result)

    def prepare(self, msg):
        pass

    def _dispatch_transition_result(self, data, result):
        return (
            result /
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
        self.log.exception(err.format(handler.name, msg, self.title))
        if amino.development:
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
            msg = tpl.format(self.title, rest)
            if amino.development:
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
            'plugin "{}" has no command "{}"'.format(self.title, name))
        return Empty()

    @may_handle(NvimIOTask)
    def message_nvim_io(self, data: Data, msg):
        msg.io.unsafe_perform_io(self.vim)

    @may_handle(RunTask)
    def message_run_task(self, data: Data, msg):
        success = lambda r: r if isinstance(r, Message) else None
        return (
            msg.task
            .unsafe_perform_sync()
            .cata(
                F(Error) >> _.pub,
                success
            )
        )

    @may_handle(DataTask)
    def message_data_task(self, data: Data, msg):
        return either_msg(
            msg.cons(Task.now(data))
            .unsafe_perform_sync()
        )

    def bubble(self, msg):
        self.parent.cata(_.bubble, lambda: self.send)(msg)


class Transitions(object):
    State = Map

    def __init__(self, machine: Machine, data: Data, msg: Message) -> None:
        self.machine = machine
        self.data = data
        self.msg = msg

    @property
    def name(self):
        return self.machine.title

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


class AsyncIOThread(threading.Thread, Logging, metaclass=abc.ABCMeta):

    def __init__(self) -> None:
        threading.Thread.__init__(self)
        self.done = None  # type: Optional[futures.Future]
        self.running = futures.Future()  # type: futures.Future

    def run(self):
        self._loop = asyncio.new_event_loop()  # type: ignore
        self._messages = asyncio.PriorityQueue(loop=self._loop)
        asyncio.set_event_loop(self._loop)
        self.done = futures.Future()
        self.running.set_result(True)
        try:
            self._loop.run_until_complete(self._main(self.init))
        except Exception:
            self.log.exception('while running state machine')
        self.running = futures.Future()

    def stop(self):
        if self.done is not None:
            self._stop()
            self.done.result(10)
            try:
                self._loop.close()
            except Exception as e:
                self.log.error(e)

    def _stop(self):
        self._done()

    def _done(self):
        self.done.set_result(True)

    @abc.abstractmethod
    async def _main(self, initial):
        ...

    @property
    def init(self):
        pass


class StateMachine(AsyncIOThread, ModularMachine):

    def __init__(self, sub: List[Machine]=List(), parent=None, title=None
                 ) -> None:
        AsyncIOThread.__init__(self)
        self.data = None
        self._messages = None
        self.sub = sub
        ModularMachine.__init__(self, parent, title=None)

    @property
    def init(self) -> Data:
        return self._data_type()

    def wait_for_running(self):
        self.running.result(3)

    def start_wait(self):
        self.start()
        self.wait_for_running()

    def _stop(self):
        self.send(Stop())

    def _publish(self, msg):
        return self._messages.put(msg)

    def send(self, msg: Message, prio=0.5):
        self.log.debug('send {}'.format(msg))
        if self._messages is not None:
            return asyncio.run_coroutine_threadsafe(  # type: ignore
                self._messages.put(msg), self._loop)

    def send_sync(self, msg: Message):
        self.send(msg)
        return self.await_state()

    def await_state(self):
        asyncio.run_coroutine_threadsafe(self.join(), self._loop)\
            .result(2)
        return self.data

    def eval_expr(self, expr: str, pre: Callable=lambda a, b: (a, b)):
        sub = self.sub
        sub_map = Map(sub / (lambda a: (a.title, a)))
        data, plugins = pre(self.data, sub_map)
        return Try(eval, expr, None, dict(data=data, plugins=plugins))

    def _send(self, data, msg: Message):
        return (
            Maybe.from_call(
                self.loop_process, data, msg, exc=TransitionFailed) |
            TransitionResult.empty(data)
        )

    @may_handle(Nop)
    def _nop(self, data: Data, msg):
        pass

    @may_handle(Stop)
    def _stop_msg(self, data: Data, msg):
        return Quit(), Done().at(1)

    @may_handle(Done)
    def _done_msg(self, data: Data, msg):
        self._done()

    @may_handle(Callback)
    def message_callback(self, data: Data, msg):
        return msg.func(data)

    @may_handle(Coroutine)
    def _couroutine(self, data: Data, msg):
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
            self.data = await self._process_one_message(self.data)

    async def _process_one_message(self, data):
        msg = await self._messages.get()
        sent = self._send(data, msg)
        result = await sent.await_coro(self._dispatch_transition_result)
        for pub in result.pub:
            await self._publish(pub)
        self._messages.task_done()
        return result.data

    async def join(self):
        await self._messages.join()


class PluginStateMachine(StateMachine):

    def __init__(self, plugins: List[str]) -> None:
        StateMachine.__init__(self)
        self.sub = plugins.flat_map(self.start_plugin)

    @may
    def start_plugin(self, path: str):
        try:
            mod = importlib.import_module(path)
        except ImportError as e:
            msg = 'invalid {} plugin module "{}": {}'
            self.log.error(msg.format(self.title, path, e))
        else:
            if hasattr(mod, 'Plugin'):
                return getattr(mod, 'Plugin')(self.vim, self)

    def plugin(self, title):
        return self.sub.find(_.title == title)

    def plug_command(self, plug_name: str, cmd_name: str, args: list=[],
                     sync=False):
        sender = self.send_sync if sync else self.send
        plug = self.plugin(plug_name)
        cmd = plug.flat_map(lambda a: a.command(cmd_name, List(args)))
        plug.ap2(cmd, PlugCommand) % sender

    def plug_command_sync(self, *a, **kw):
        return self.plug_command(*a, sync=True, **kw)

    @may_handle(PlugCommand)
    def _plug_command(self, data, msg):
        self.log.debug(
            'sending command {} to plugin {}'.format(msg.msg, msg.plug.title))
        return msg.plug.process(data, msg.msg)


class RootMachine(PluginStateMachine, HasNvim, Logging):

    def __init__(self, vim: NvimFacade, plugins: List[str]=List()) -> None:
        HasNvim.__init__(self, vim)
        PluginStateMachine.__init__(self, plugins)

    @property
    def title(self):
        return 'ribosome'

__all__ = ('Machine', 'Message', 'StateMachine', 'PluginStateMachine', 'Error',
           'Info', 'ModularMachine', 'Transitions')
