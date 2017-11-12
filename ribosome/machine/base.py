import time
import uuid
import inspect
from typing import Callable, TypeVar, Type, Any, Generic, Generator
import asyncio

import toolz

from amino import Maybe, _, List, Map, Empty, L, __, Just, Either, Lists, Left, Right, IO, Nothing, Boolean, _
from amino.util.string import camelcaseify, ToStr
from amino.lazy import lazy
from amino.func import flip
from amino.state import EitherState, EvalState
from amino.do import tdo

from ribosome.machine.message_base import Message
from ribosome.logging import print_ribo_log_info, ribo_log
from ribosome.data import Data
from ribosome.nvim import NvimIO, NvimFacade
from ribosome.machine.machine import Machine
from ribosome.machine.transition import (Handler, TransitionResult, may_handle, Error, Debug, handle, _io_result,
                                         _recover_error, DynHandler, TransitionLog)
from ribosome.request.command import StateCommand
from ribosome.process import NvimProcessExecutor
from ribosome.machine.messages import (RunNvimIO, RunIO, UnitIO, RunCorosParallel, SubProcessSync, RunIOsParallel,
                                       ShowLogInfo, Nop, RunIOAlg, TransitionException, Info, RunNvimIOAlg, DataIO,
                                       RunNvimUnitIO, RunNvimIOStateAlg)
from ribosome.machine.handler import Handlers, DynHandlerJob, AlgHandlerJob, HandlerJob
from ribosome.machine import trans
from ribosome.machine.trans import Propagate, Transit

A = TypeVar('A')
D = TypeVar('D', bound=Data)
TransState = EvalState[TransitionLog, TransitionResult]


def nio(f: Callable[[NvimFacade], Any]) -> RunNvimIO:
    return RunNvimIO(NvimIO(f))


def unit_nio(f: Callable[[NvimFacade], None]) -> RunNvimUnitIO:
    return RunNvimUnitIO(NvimIO(f))


def handlers(cls: Type['MachineBase']) -> List[Handler]:
    return Lists.wrap(inspect.getmembers(cls, Boolean.is_a(Handler))) / _[1]


def message_handlers(handlers: List[Handler]) -> Map[float, Handlers]:
    def create(prio, h):
        h = List.wrap(h).apzip(_.message).map2(flip)
        return prio, Handlers(prio, Map(h))
    return Map(toolz.groupby(_.prio, handlers)).map(create)


class MachineBase(Generic[D], Machine, ToStr):
    _data_type = Data

    def __init__(self, name: str, parent: Maybe[Machine]=Nothing) -> None:
        self._name = name
        self._parent = parent
        self.uuid = uuid.uuid4()
        self._reports = List()
        self._min_report_time = 0.1

    def _arg_desc(self) -> List[str]:
        return List(self.name)

    @property
    def name(self) -> str:
        return self._name

    @property
    def parent(self) -> Maybe[Machine]:
        return self._parent

    @property
    def title(self) -> str:
        return self.name

    @lazy
    def _message_handlers(self):
        return message_handlers(handlers(type(self)))

    @property
    def _default_handler(self):
        return DynHandler(self, 'internal', type(self).internal, None, 0, True)

    @property
    def prios(self) -> List[float]:
        return self._message_handlers.k

    def handler_job_type(self, handler: Handler) -> Type[HandlerJob]:
        return DynHandlerJob if handler.dyn else AlgHandlerJob

    def process(self, data: D, msg: Message, prio: float=None) -> TransState:
        self.prepare(msg)
        def execute(handler: Callable) -> TransitionResult:
            self.log.debug(f'handling {msg} in {self.name}')
            job = HandlerJob.from_handler(handler.name, handler, data, msg)
            result = job.run(self)
            self._check_time(job.start_time, msg)
            return EvalState.pure(result)
        return self._resolve_handler(msg, prio) / execute | (lambda: self.internal(data, msg))

    def prepare(self, msg):
        pass

    def loop_process(self, data: D, msg: Message, prio: float=None) -> TransState:
        @tdo(TransState)
        def loop(current: TransitionResult, m: Message, prio: float=None) -> Generator:
            result = yield self.process(current.data, m, prio)
            log = yield EvalState.get()
            resend = result.resend
            next = current.accum(result)
            new_log, next_msg = log.resend(resend).pop
            yield EvalState.set(new_log)
            yield next_msg / L(loop)(next, _) | EvalState.pure(next)
        return loop(TransitionResult.empty(data), msg, prio)

    @tdo(TransState)
    def process_message(self, data: D, msg: Message, prio: float=None) -> Generator:
        yield EvalState.modify(__.log(msg))
        yield self.loop_process(data, msg, prio)

    def _resolve_handler(self, msg: Message, prio: float) -> Maybe[Callable]:
        f = __.handler(msg)
        return (
            self._message_handlers.v.find_map(f)
            if prio is None else
            (self._message_handlers.get(prio) // f)
        )

    def internal(self, data: D, msg: Message) -> TransState:
        return self.unhandled(data, msg)

    def unhandled(self, data: D, msg: Message) -> TransState:
        return EvalState.pure(TransitionResult.unhandled(data))

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

    @trans.relay(RunNvimIOStateAlg)
    def message_run_nvim_io_state_alg(self, data: D, msg: RunNvimIOAlg) -> Either[str, List[Message]]:
        return Transit(EitherState.apply(self._run_nio(msg.io_f).join))

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
