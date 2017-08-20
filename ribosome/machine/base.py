import time
import uuid
import inspect
from typing import Callable, TypeVar, Type
import asyncio

import toolz

from amino import Maybe, _, List, Map, Empty, L, __, Just, Either, Lists, Left, Right
from amino.util.string import camelcaseify
from amino.task import Task
from amino.lazy import lazy
from amino.func import flip

from ribosome.machine.message_base import Message
from ribosome.logging import print_ribo_log_info
from ribosome.data import Data
from ribosome.nvim import NvimIO
from ribosome.machine.interface import MachineI
from ribosome.machine.transition import (Handler, TransitionResult, may_handle, Error, Debug, handle, _task_result,
                                         _recover_error, DynHandler)
from ribosome.machine.message_base import _machine_attr
from ribosome.request.command import StateCommand
from ribosome.process import NvimProcessExecutor
from ribosome.machine.messages import (NvimIOTask, RunIO, UnitTask, DataTask, RunCorosParallel, SubProcessSync,
                                       RunIOsParallel, ShowLogInfo, Nop, RunIOAlg, TransitionException)
from ribosome.machine.handler import Handlers, DynHandlerJob, AlgHandlerJob, HandlerJob, AlgResultValidator
from ribosome.machine import trans

A = TypeVar('A')


def io(f: Callable):
    return NvimIOTask(NvimIO(f))


class MachineBase(MachineI):
    _data_type = Data

    def __init__(self, parent: 'Machine'=None, title=None) -> None:
        self.parent = Maybe(parent)
        self._title = Maybe(title)
        self.uuid = uuid.uuid4()
        self._reports = List()
        self._min_report_time = 0.1

    @property
    def title(self):
        return self._title.or_else(
            List.wrap(type(self).__module__.rsplit('.')).reversed.lift(1)
        ) | 'machine'

    @lazy
    def _message_handlers(self):
        def create(prio, h):
            h = List.wrap(h).apzip(_.message).map2(flip)
            return prio, Handlers(prio, Map(h))
        return Map(toolz.groupby(_.prio, self._handlers)).map(create)

    @property
    def _handlers(self):
        methods = inspect.getmembers(type(self), lambda a: hasattr(a, _machine_attr))
        return List.wrap(methods).map2(L(Handler.create)(self, _, _))

    @property
    def _default_handler(self):
        return DynHandler(self, 'unhandled', type(self).unhandled, None, 0, True)

    @property
    def prios(self):
        return self._message_handlers.k

    def handler_job_type(self, handler: Handler) -> Type[HandlerJob]:
        return DynHandlerJob if handler.dyn else AlgHandlerJob

    def process(self, data: Data, msg, prio=None) -> TransitionResult:
        self.prepare(msg)
        handler = self._resolve_handler(msg, prio)
        job = self.handler_job_type(handler)(self, data, msg, handler, self._data_type)
        result = job.run()
        self._check_time(job.start_time, msg)
        return result

    def prepare(self, msg):
        pass

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

    def unhandled(self, data: Data, msg: Message):
        return Just(TransitionResult.unhandled(data))

    def _command_by_message_name(self, name: str):
        msg_name = camelcaseify(name)
        return (
            self._message_handlers.to_list
            .sort_by(__[0])
            .map2(lambda a, b: b.handlers)
            .find_map(__.find_key(lambda a: a.__name__ in [name, msg_name]))
        )

    def command(self, name: str, args: list):
        return (
            self._command_by_message_name(name)
            .map(lambda a: StateCommand(a[0]))
            .map(__.dispatch(self, args))
            .or_else(L(self._invalid_command)(name, _))
        )

    def _invalid_command(self, name):
        self.log.error(
            'plugin "{}" has no command "{}"'.format(self.title, name))
        return Empty()

    @may_handle(NvimIOTask)
    def message_nvim_io(self, data: Data, msg):
        msg.io.unsafe_perform_io(self.vim)

    def _run_io(self, task):
        result = task.attempt
        if result.value is None:
            self.log.error('Task returned None: {}'.format(task))
        return _task_result(result)

    @handle(RunIO)
    def message_run_io(self, data: Data, msg):
        return self._run_io(msg.task)

    @trans.relay(RunIOAlg)
    def message_run_io_alg(self, data: Data, msg: RunIOAlg):
        return self._run_io(msg.io)

    @handle(UnitTask)
    def message_run_unit_task(self, data: Data, msg):
        return self._run_io(msg.task.replace(Just(Nop())))

    @handle(DataTask)
    def message_data_task(self, data: Data, msg):
        return self._run_io(msg.cons(Task.now(data)))

    @may_handle(RunCorosParallel)
    def run_coros_parallel(self, data: Data, msg: RunCorosParallel) -> Message:
        async def wrap() -> Either[str, List[Message]]:
            try:
                results = await asyncio.gather(*msg.coros)
            except Exception as e:
                self.log.caught_exception('running coroutines', e)
                return Left(f'running coros failed: {e}')
            else:
                return Lists.wrap(results).traverse(L(_recover_error)('parallel coros', _), Maybe)
        return wrap()

    @may_handle(SubProcessSync)
    async def sub_process_sync(self, data: Data, msg: SubProcessSync) -> Message:
        executor = NvimProcessExecutor(self.vim)
        return msg.result(await executor.run(msg.job))

    @may_handle(RunIOsParallel)
    def run_ios_parallel(self, data: Data, msg: RunIOsParallel) -> Message:
        coros = msg.ios / _.coro
        async def wrap() -> Maybe[List[Message]]:
            try:
                results = await asyncio.gather(*coros)
            except Exception as e:
                self.log.caught_exception('running coroutines', e)
                return Left(f'running coros failed: {e}')
            else:
                return Right(
                    Lists.wrap(results) /
                    __.value_or(lambda a: TransitionException('running IOs in parallel', a.cause).pub)
                )
        return wrap()

    @may_handle(Error)
    def message_error(self, data, msg):
        self.log.error(msg.message)

    @may_handle(TransitionException)
    def transition_exception(self, data, msg):
        self.log.caught_exception(msg.context, msg.exc)

    @may_handle(Debug)
    def message_debug(self, data, msg):
        self.log.debug(msg.message)

    @may_handle(ShowLogInfo)
    def show_log_info(self, data: Data, msg: ShowLogInfo) -> Message:
        print_ribo_log_info(self.log.verbose)

    def bubble(self, msg):
        self.parent.cata(_.bubble, lambda: self.send)(msg)

    def _check_time(self, start_time, msg):
        dur = time.time() - start_time
        self.log.debug(self._format_report(msg, dur))
        if dur > self._min_report_time:
            self._reports = self._reports.cat((msg, dur))

    def report(self):
        if self._reports:
            self.log.info('time-consuming messages in {}:'.format(self.title))
            self._reports.map2(self._format_report) % self.log.info

    def _format_report(self, msg, dur):
        return '{} took {:.4f}s for {} to process'.format(msg, dur, self.title)

__all__ = ('MachineBase',)
