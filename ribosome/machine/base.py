import time
import uuid
import inspect
from typing import Sequence, Callable, TypeVar
from asyncio import iscoroutine

import toolz

import amino
from amino import Maybe, F, _, List, Map, Empty, curried, L, __, Just
from amino.util.string import camelcaseify
from amino.task import Task
from amino.lazy import lazy
from amino.func import flip

from ribosome.machine.message_base import Message, Publish, message
from ribosome.logging import Logging
from ribosome.data import Data
from ribosome.nvim import NvimIO
from ribosome.machine.transition import (Handler, TransitionResult,
                                         CoroTransitionResult,
                                         StrictTransitionResult, may_handle,
                                         TransitionFailed, Coroutine,
                                         MachineError, WrappedHandler, Error,
                                         Debug, handle, _task_result)
from ribosome.machine.message_base import _machine_attr, Nop
from ribosome.request.command import StateCommand

A = TypeVar('A')

NvimIOTask = message('NvimIOTask', 'io')
RunTask = message('RunTask', 'task')
UnitTask = message('UnitTask', 'task')
DataTask = message('DataTask', 'cons')
DataEitherTask = message('DataEitherTask', 'cons')


def is_seq(a):
    return isinstance(a, Sequence)


def is_message(a):
    return isinstance(a, Message)


def io(f: Callable):
    return NvimIOTask(NvimIO(f))


class Handlers(Logging):

    def __init__(self, prio: int, handlers: Map[type, Handler]) -> None:
        self.prio = prio
        self.handlers = handlers

    def handler(self, msg):
        return self.handlers.get(type(msg))


class Machine(Logging):
    _data_type = Data

    def __init__(self, parent: 'Machine'=None, title=None) -> None:
        self.parent = Maybe(parent)
        self._title = Maybe(title)
        self.uuid = uuid.uuid4()
        self._message_handlers = self._handler_map()

    @property
    def title(self):
        return self._title.or_else(
            List.wrap(type(self).__module__.rsplit('.')).reversed.lift(1)
        ) | 'machine'

    def _handler_map(self):
        def create(prio, h):
            h = List.wrap(h).apzip(_.message).map2(flip)
            return prio, Handlers(prio, Map(h))
        return Map(toolz.groupby(_.prio, self._handlers)).map(create)

    @property
    def _handlers(self):
        methods = inspect.getmembers(type(self),
                                     lambda a: hasattr(a, _machine_attr))
        return List.wrap(methods).map2(L(Handler.create)(self, _, _))

    @property
    def _default_handler(self):
        return Handler(self, 'unhandled', None, type(self).unhandled, 0)

    @property
    def prios(self):
        return self._message_handlers.k

    def process(self, data: Data, msg, prio=None) -> TransitionResult:
        self.prepare(msg)
        handler = self._resolve_handler(msg, prio)
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

    def loop_process(self, data, msg, prio=None):
        sender = lambda z, m: z.accum(self.loop_process(z.data, m))
        return self.process(data, msg, prio).fold(sender)

    def _resolve_handler(self, msg, prio):
        f = __.handler(msg)
        return (
            self._message_handlers.v.find_map(f)
            if prio is None else
            (self._message_handlers.get(prio) // f)
        ) | (lambda: self._default_handler)

    def _execute_transition(self, handler, data, msg):
        start_time = time.time()
        try:
            return handler.run(data, msg)
        except Exception as e:
            return self._handle_transition_error(handler, msg, e)
        finally:
            dur = time.time() - start_time
            self.log.debug('{} took {:.4f}s for {} to process'.format(
                msg, dur, self.title))

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
        elif is_message(result) or not is_seq(result):
            result = List(result)
        datas, rest = List.wrap(result).split_type(self._data_type)
        trans = rest / self._transform_result
        msgs, rest = trans.split_type(Message)
        if rest:
            tpl = 'invalid transition result parts in {}: {}'
            msg = tpl.format(self.title, rest)
            if amino.development:
                raise MachineError(msg)
            else:
                self.log.error(msg)
        new_data = datas.head | old_data
        return self._create_result(new_data, msgs)

    def _transform_result(self, result):
        if iscoroutine(result):
            return Coroutine(result).pub
        elif isinstance(result, Task):
            return RunTask(result)
        else:
            return result

    def _create_result(self, data, msgs):
        pub, resend = msgs.split_type(Publish)
        pub_msgs = pub.map(_.message)
        return StrictTransitionResult(data=data, pub=pub_msgs, resend=resend)

    def unhandled(self, data: Data, msg: Message):
        return Just(TransitionResult.unhandled(data))

    def _command_by_message_name(self, name: str):
        msg_name = camelcaseify(name)
        return self._message_handlers\
            .find_key(lambda a: a.__name__ in [name, msg_name])

    def command(self, name: str, args: list):
        return self._command_by_message_name(name)\
            .map(lambda a: StateCommand(a[0]))\
            .map(__.dispatch(self, args))\
            .or_else(F(self._invalid_command, name))

    def _invalid_command(self, name):
        self.log.error(
            'plugin "{}" has no command "{}"'.format(self.title, name))
        return Empty()

    @may_handle(NvimIOTask)
    def message_nvim_io(self, data: Data, msg):
        msg.io.unsafe_perform_io(self.vim)

    def _run_task(self, task):
        result = task.attempt()
        if result.value is None:
            self.log.error('Task returned None: {}'.format(task))
        return _task_result(result)

    @handle(RunTask)
    def message_run_task(self, data: Data, msg):
        return self._run_task(msg.task)

    @handle(UnitTask)
    def message_run_unit_task(self, data: Data, msg):
        return self._run_task(msg.task.replace(Just(Nop())))

    @handle(DataTask)
    def message_data_task(self, data: Data, msg):
        return self._run_task(msg.cons(Task.now(data)))

    @may_handle(Error)
    def message_error(self, data, msg):
        self.log.error(msg.message)

    @may_handle(Debug)
    def message_debug(self, data, msg):
        self.log.debug(msg.message)

    def bubble(self, msg):
        self.parent.cata(_.bubble, lambda: self.send)(msg)


class Transitions:
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


class ModularMachine(Machine):
    Transitions = Transitions

    @property
    def _handlers(self):
        methods = inspect.getmembers(self.Transitions,
                                     lambda a: hasattr(a, _machine_attr))
        handlers = (
            List.wrap(methods)
            .map2(L(WrappedHandler.create)(self, _, self.Transitions, _))
        )
        return handlers + super()._handlers

__all__ = ('ModularMachine', 'Transitions', 'Machine')
