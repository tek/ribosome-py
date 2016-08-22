import inspect
from typing import Sequence, Callable, TypeVar
from asyncio import iscoroutine

import amino
from amino import Maybe, may, F, _, List, Map, Empty, curried, L
from amino.util.string import camelcaseify
from amino.task import Task
from amino.lazy import lazy

from ribosome.machine.message_base import Message, Publish, message
from ribosome.logging import Logging
from ribosome.data import Data
from ribosome.nvim import NvimIO
from ribosome.machine.transition import (Handler, TransitionResult,
                                         CoroTransitionResult,
                                         StrictTransitionResult, may_handle,
                                         either_msg, TransitionFailed,
                                         Coroutine, MachineError, Error,
                                         WrappedHandler)
from ribosome.machine.message_base import _machine_attr
from ribosome.cmd import StateCommand

A = TypeVar('A')

NvimIOTask = message('NvimIOTask', 'io')
RunTask = message('RunTask', 'task')
DataTask = message('DataTask', 'cons')
DataEitherTask = message('DataEitherTask', 'cons')


def is_seq(a):
    return isinstance(a, Sequence)


def is_message(a):
    return isinstance(a, Message)


def io(f: Callable):
    return NvimIOTask(NvimIO(f))


class Machine(Logging):
    _data_type = Data

    def __init__(self, parent: 'Machine'=None, title=None) -> None:
        self.parent = Maybe(parent)
        self._title = Maybe(title)
        self._message_handlers = self._collect_handlers()

    @property
    def title(self):
        return self._title.or_else(
            List.wrap(type(self).__module__.rsplit('.')).reversed.lift(1)
        ) | 'machine'

    def _collect_handlers(self):
        handlers = inspect.getmembers(type(self),
                                      lambda a: hasattr(a, _machine_attr))
        handler_map = (
            List.wrap(handlers)
            .map2(L(Handler.create)(self, _, _))
            .map(lambda a: (a.message, a))
        )
        return Map(handler_map)

    @property
    def _default_handler(self):
        return Handler(self, 'unhandled', None, type(self).unhandled)

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
        elif is_message(result) or not is_seq(result):
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

    @may_handle(DataEitherTask)
    def message_data_either_task(self, data: Data, msg):
        return either_msg(
            msg.cons(Task.now(data))
            .map(either_msg)
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


class ModularMachine(Machine):
    Transitions = Transitions

    def _collect_handlers(self):
        handlers = inspect.getmembers(self.Transitions,
                                      lambda a: hasattr(a, _machine_attr))
        handler_map = (
            List.wrap(handlers)
            .map2(L(WrappedHandler.create)(self, _, self.Transitions, _))
            .map(lambda a: (a.message, a))
        )
        return super()._collect_handlers() ** handler_map


__all__ = ('ModularMachine', 'Transitions', 'Machine')
