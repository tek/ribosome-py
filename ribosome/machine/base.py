import time
import uuid
import inspect
from typing import Callable, TypeVar, Type, Any, Generic
import asyncio

import toolz

from amino import Maybe, _, List, Map, Empty, L, __, Just, Either, Lists, Left, Right, IO
from amino.util.string import camelcaseify
from amino.io import IO
from amino.lazy import lazy
from amino.func import flip

from ribosome.machine.message_base import Message
from ribosome.logging import print_ribo_log_info
from ribosome.data import Data
from ribosome.nvim import NvimIO, NvimFacade
from ribosome.machine.interface import MachineI
from ribosome.machine.transition import (Handler, TransitionResult, may_handle, Error, Debug, handle, _io_result,
                                         _recover_error, DynHandler)
from ribosome.machine.message_base import _machine_attr
from ribosome.request.command import StateCommand
from ribosome.process import NvimProcessExecutor
from ribosome.machine.messages import (RunNvimIO, RunIO, UnitIO, RunCorosParallel, SubProcessSync, RunIOsParallel,
                                       ShowLogInfo, Nop, RunIOAlg, TransitionException, Info, RunNvimIOAlg, DataIO,
                                       RunNvimUnitIO)
from ribosome.machine.handler import Handlers, DynHandlerJob, AlgHandlerJob, HandlerJob
from ribosome.machine import trans
from ribosome.machine.trans import Propagate

A = TypeVar('A')
D = TypeVar('D', bound=Data)


def nio(f: Callable[[NvimFacade], Any]) -> RunNvimIO:
    return RunNvimIO(NvimIO(f))


def unit_nio(f: Callable[[NvimFacade], None]) -> RunNvimUnitIO:
    return RunNvimUnitIO(NvimIO(f))


class MachineBase(Generic[D], MachineI):
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

    def process(self, data: D, msg, prio=None) -> TransitionResult:
        self.prepare(msg)
        handler = self._resolve_handler(msg, prio)
        job = self.handler_job_type(handler)(self, data, msg, handler, self._data_type)
        result = job.run()
        self._check_time(job.start_time, msg)
        return result

    def prepare(self, msg):
        pass

    def loop_process(self, data, msg, prio=None):
        def loop(z, m) -> None:
            self.parent % __.log_message(m, self.title)
            return z.accum(self.loop_process(z.data, m))
        return self.process(data, msg, prio).fold(loop)

    def log_message(self, msg: Message, name: str) -> None:
        pass

    def _resolve_handler(self, msg, prio):
        f = __.handler(msg)
        return (
            self._message_handlers.v.find_map(f)
            if prio is None else
            (self._message_handlers.get(prio) // f)
        ) | (lambda: self._default_handler)

    def unhandled(self, data: D, msg: Message):
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
            .or_else(L(self._invalid_command)(name))
        )

    def _invalid_command(self, name):
        self.log.error('plugin "{}" has no command "{}"'.format(self.title, name))
        return Empty()

    @may_handle(RunNvimUnitIO)
    def message_run_nvim_unit_io(self, data: D, msg: RunNvimUnitIO):
        msg.io.unsafe_perform_io(self.vim)

    def _run_nio(self, io: RunNvimIOAlg) -> Either[str, List[Message]]:
        result = io.attempt(self.vim)
        if result.value is None:
            self.log.error(f'NvimIO returned None: {io}')
        return result

    @trans.multi(RunNvimIO, trans.e)
    def message_run_nvim_io(self, data: D, msg: RunNvimIO) -> Either[str, List[Message]]:
        return self._run_nio(msg.io)

    @trans.relay(RunNvimIOAlg)
    def message_run_nvim_io_alg(self, data: D, msg: RunNvimIOAlg) -> Either[str, List[Message]]:
        return Propagate.from_either(self._run_nio(msg.io))

    def _run_io(self, io: IO[A]) -> Either[str, List[Message]]:
        result = io.attempt
        if result.value is None:
            self.log.error(f'IO returned None: {io}')
        return _io_result(result)

    @handle(RunIO)
    def message_run_io(self, data: D, msg):
        return self._run_io(msg.io)

    @trans.relay(RunIOAlg)
    def message_run_io_alg(self, data: D, msg: RunIOAlg):
        return self._run_io(msg.io)

    @handle(UnitIO)
    def message_run_unit_io(self, data: D, msg):
        return self._run_io(msg.io.replace(Just(Nop())))

    @handle(DataIO)
    def message_data_io(self, data: D, msg):
        return self._run_io(msg.cons(IO.now(data)))

    @may_handle(RunCorosParallel)
    def message_run_coros_parallel(self, data: D, msg: RunCorosParallel) -> Message:
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
    async def message_sub_process_sync(self, data: D, msg: SubProcessSync) -> Message:
        executor = NvimProcessExecutor(self.vim)
        await executor.run(msg.job)
        return msg.result(msg.job.result)

    @may_handle(RunIOsParallel)
    def message_run_ios_parallel(self, data: D, msg: RunIOsParallel) -> Message:
        coros = msg.ios / _.coro
        async def wrap() -> Maybe[List[Message]]:
            try:
                results = await asyncio.gather(*coros)
            except Exception as e:
                self.log.caught_exception('running coroutines', e)
                return Left(TransitionException('running coroutines', e))
            else:
                return Right(
                    Lists.wrap(results) /
                    __.value_or(lambda a: TransitionException('running IOs in parallel', a.cause).pub)
                )
        return wrap()

    @may_handle(Error)
    def message_error(self, data: D, msg: Error) -> None:
        self.log.error(msg)

    @may_handle(Info)
    def message_info(self, data: D, msg: Info) -> None:
        self.log.info(msg.message)

    @may_handle(TransitionException)
    def transition_exception(self, data, msg):
        self.log.caught_exception(msg.context, msg.exc)

    @may_handle(Debug)
    def message_debug(self, data, msg):
        self.log.debug(msg.message)

    @may_handle(ShowLogInfo)
    def show_log_info(self, data: D, msg: ShowLogInfo) -> Message:
        print_ribo_log_info(self.log.verbose)

    def bubble(self, msg):
        self.parent.cata(_.bubble, lambda: self.send)(msg)

    def _check_time(self, start_time, msg):
        dur = time.time() - start_time
        self.log.debug1(self._format_report, msg, dur)
        if dur > self._min_report_time:
            self._reports = self._reports.cat((msg, dur))

    def report(self):
        if self._reports:
            self.log.info('time-consuming messages in {}:'.format(self.title))
            self._reports.map2(self._format_report) % self.log.info

    def _format_report(self, msg, dur):
        return '{} took {:.4f}s for {} to process'.format(msg, dur, self.title)

__all__ = ('MachineBase',)
