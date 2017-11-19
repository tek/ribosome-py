from typing import Callable, TypeVar, Generic, Generator, Any
import abc
import threading
import asyncio
from contextlib import contextmanager
from concurrent.futures import Future as CFuture, TimeoutError

from ribosome.logging import Logging
from ribosome.data import Data
from ribosome.nvim import HasNvim, ScratchBuilder
from ribosome import NvimFacade
from ribosome.machine.message_base import Message, Envelope
from ribosome.machine.base import Machine, MachineBase, TransState
from ribosome.machine.transition import may_handle, handle, _recover_error, CoroExecutionHandler, TransitionLog
from ribosome.machine.messages import Nop, PlugCommand, Stop, Error
from ribosome.machine.handler import DynHandlerJob
from ribosome.machine.internal import RunScratchMachine, RunMachine
from ribosome.config import AutoData

import amino
from amino import Maybe, Map, Try, _, L, List, Nothing, Lists, Nil
from amino.util.string import red, blue
from amino.state import EvalState
from amino.do import do

short_timeout = 3
medium_timeout = 3
long_timeout = 5
warn_no_handler = True


class AsyncIOBase(Logging, abc.ABC):

    def __init__(self) -> None:
        self._messages: asyncio.PriorityQueue = None

    def _init_asyncio(self):
        self._loop = (
            asyncio.new_event_loop()
            if asyncio._get_running_loop() is None  # type: ignore
            else asyncio.get_event_loop()
        )
        self._messages = asyncio.PriorityQueue(loop=self._loop)

    @abc.abstractmethod
    def stop(self, shutdown=True) -> None:
        ...


D = TypeVar('D', bound=AutoData)


class StateMachineBase(Generic[D], MachineBase):

    def __init__(self, name: str, sub: List[Machine], parent: Maybe[Machine]=Nothing, debug: bool=False
                 ) -> None:
        self.sub = sub
        self.debug = debug
        self._messages: asyncio.PriorityQueue = None
        self.message_log = List()
        ModularMachine.__init__(self, name, parent)

    def start_wait(self):
        self.start()
        self.wait_for_running()

    def _stop(self):
        self.send_sync(Stop())

    def _publish(self, msg):
        return self._messages.put(msg)

    def send(self, msg: Message):
        if self._messages is not None:
            return asyncio.run_coroutine_threadsafe(self._messages.put(msg), self._loop)

    def send_sync(self, msg: Message, wait=None):
        self.send(msg)
        return self.await_state(wait)

    def await_state(self, wait=None):
        asyncio.run_coroutine_threadsafe(self.join_messages(), self._loop).result(Maybe(wait) | short_timeout)
        return self.data

    def eval_expr(self, expr: str, pre: Callable=lambda a, b: (a, b)):
        sub = self.sub
        sub_map = Map(sub / (lambda a: (a.title, a)))
        data, components = pre(self.data, sub_map)
        return Try(eval, expr, None, dict(data=data, components=components))

    def _send(self, data, msg: Message) -> Any:
        self.log_message(msg, self.name)
        result = self.loop_process(data, msg).run(TransitionLog(List(msg), Nil))
        return (
            Try(result.evaluate)
            .value_or(L(TransitionResult.failed)(data, _))
        )

    def log_message(self, msg: Message, name: str) -> None:
        self.append_message_log(msg, name)

    def append_message_log(self, msg: Message, name: str) -> None:
        self.log.debug('processing {} in {}'.format(msg, name))
        if self.debug:
            self.message_log.append(msg)

    def unhandled(self, data: D, msg: Message) -> TransState:
        prios = (self.sub // _.prios).distinct.sort(reverse=True)
        @do(TransState)
        def step(z: TransState, a: float) -> Generator:
            current = yield z
            yield EvalState.pure(current) if current.handled else self._fold_sub(current.data, msg, a)
        return prios.fold_left(EvalState.pure(TransitionResult.unhandled(data)))(step)

    def _fold_sub(self, data: D, msg: Message, prio: float=None) -> TransState:
        ''' send **msg** to all submachines, passing the transformed data from each machine to the next and
        accumulating published messages.
        '''
        @do(TransState)
        def send(z: TransState, sub: Machine) -> Generator:
            current = yield z
            next = yield sub.loop_process(current.data, msg, prio)
            yield EvalState.pure(current.accum(next))
        return self.sub.fold_left(EvalState.pure(TransitionResult.unhandled(data)))(send)

    @contextmanager
    def transient(self):
        self.start()
        self.wait_for_running()
        self.send(Nop())
        yield self
        self.stop()

    async def _execute_coro_result(self, data: Data, msg: Message, ctr: Any) -> None:
        try:
            job = DynHandlerJob(self, data, msg, CoroExecutionHandler(self, 'coroutine result', msg, None, 1.0, True),
                                self._data_type)
        except Exception as e:
            return TransitionResult.failed(data, f'failed to create coro handler job: {e}')
        try:
            result0 = await ctr.coro.coro
            result = job.dispatch_transition_result(_recover_error(self, result0))
        except Exception as e:
            return job.handle_transition_error(e)
        else:
            if result.resend:
                msg = 'Cannot resend {} from coro {}, use .pub on messages'
                self.log.warn(msg.format(result.resend, ctr.coro))
            return result

    async def join_messages(self):
        await self._messages.join()


class MessageProcessor(Logging):

    def __init__(
            self,
            messages: asyncio.PriorityQueue,
            send: Callable[[D, Message], Any]
    ) -> None:
        self.messages = messages
        self.send = send
        self.message_log = Nil

    async def process_one_message(self, data: D) -> D:
        raw = await self.messages.get()
        msg = raw.delivery if isinstance(raw, Envelope) else raw
        log, sent = self.send(data, msg)
        self.message_log = self.message_log + log.message_log
        result = (
            self.failed_transition(msg, sent)
            if sent.failure else
            await self.successful_transition(data, msg, sent)
            if sent.handled else
            self.unhandled_message(msg, sent)
        )
        self.messages.task_done()
        return result.data

    async def loop_messages(self, data: D) -> D:
        next = await self.process_one_message(data)
        return data if self.messages.empty() else await self.loop_messages(next)

    def failed_transition(self, msg: Message, sent: Any) -> Any:
        msg_name = type(msg).__name__
        def log_error() -> None:
            errmsg = sent.error_message
            self.log.error(Error(errmsg, prefix=f'''{red('error')} handling {blue(msg_name)}'''))
        def log_exc(e: Exception) -> None:
            self.log.caught_exception_error(f'handling {blue(msg_name)}', e)
        def log_verbose() -> None:
            sent.exception / log_exc
        try:
            log_error()
            if amino.development:
                log_verbose()
        except Exception as e:
            self.log.error(f'error in `failed_transition`: {e}')
        return sent

    async def successful_transition(self, data: D, msg: Message, sent: Any) -> Any:
        result = (
            await self._execute_coro_result(data, msg, sent)
            if isinstance(sent, CoroTransitionResult) else
            sent
        )
        for pub in result.pub:
            await self.messages.put(pub)
        return result

    def unhandled_message(self, msg, sent):
        log = self.log.warning if warn_no_handler else self.log.debug
        log(f'no handler for {msg}')
        return sent


class StateMachine(StateMachineBase, AsyncIOBase):

    def __init__(self, name: str, sub: List[Machine], parent: Maybe[Machine]=Nothing, debug: bool=False) -> None:
        StateMachineBase.__init__(self, name, sub, parent, debug)
        AsyncIOBase.__init__(self)
        self.last_message_log = Nil

    def start(self) -> None:
        self.log.debug(f'starting event loop in {self}')
        self.data = self.init
        self._init_asyncio()

    def stop(self, shutdown=True) -> None:
        pass

    def wait_for_running(self) -> None:
        pass

    def send_and_process(self, data: D, msg: Message) -> D:
        if self._messages is not None:
            self._messages.put_nowait(msg)
            if not self._loop.is_running():
                try:
                    proc = MessageProcessor(self._messages, self._send)
                    result = self._loop.run_until_complete(proc.loop_messages(data))
                    self.last_message_log = proc.message_log
                    return result
                except Exception as e:
                    self.log.caught_exception('submitting `_process_messages` coro to loop', e)
        else:
            self.log.debug(f'tried to send {msg} while `_messages` was None')

    def send_thread(self, msg: Message, asy: bool) -> None:
        a = 'a' if asy else ''
        desc = f'send {msg} {a}sync at {msg.prio} in {self.name}'
        self.log.debug(desc)
        done = CFuture()
        def run() -> None:
            try:
                self.data = self.send_and_process(self.data, msg)
            except Exception as e:
                self.log.caught_exception_error(desc, e)
                done.set_result(False)
            else:
                done.set_result(True)
        threading.Thread(target=run).start()
        return done

    def send_sync(self, msg, timeout=long_timeout) -> None:
        try:
            self.send_thread(msg, False).result(timeout)
        except TimeoutError as e:
            self.log.warn(f'timed out waiting for processing of {msg} in {self.name}')
        return self.data

    def send(self, msg: Message) -> CFuture:
        return self.send_sync(msg)


class PluginStateMachine(StateMachine, HasNvim):

    def __init__(self, name: str, vim: NvimFacade, sub: List[Machine], parent: Maybe[Machine]=Nothing, debug: bool=False
                 ) -> None:
        debug = vim.vars.p('debug') | False
        HasNvim.__init__(self, vim)
        StateMachine.__init__(self, name, sub, parent, debug)

    def component(self, name: str) -> Maybe[MachineBase]:
        return self.sub.find(_.name == name)

    def plug_command(self, plug_name: str, cmd_name: str, args: tuple=(), sync=False):
        sender = self.send_sync if sync else self.send
        plug = self.component(plug_name)
        cmd = plug.flat_map(lambda a: a.command(cmd_name, Lists.wrap(args)))
        plug.ap2(cmd, PlugCommand) % sender

    def plug_command_sync(self, *a, **kw):
        return self.plug_command(*a, sync=True, **kw)

    @may_handle(PlugCommand)
    def _plug_command(self, data, msg):
        self.log.debug('sending command {} to component {}'.format(msg.msg, msg.plug.name))
        self.log_message(msg.msg, self.name)
        return msg.plug.process(data, msg.msg)

    @handle(RunScratchMachine)
    def _scratch_machine(self, data, msg):
        return (
            ScratchBuilder(**(msg.options - 'init'))
            .build
            .unsafe_perform_io(self.vim) /
            L(msg.machine)(_, self) /
            L(RunMachine)(_, msg.options)
        )

__all__ = ('StateMachine', 'PluginStateMachine', 'StateMachineBase', 'StateMachine')
