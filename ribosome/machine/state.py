import time
from typing import Callable, Awaitable, Generator, Any, Union, TypeVar, Generic, Type
from typing import Optional  # noqa
import abc
import threading
import asyncio
from contextlib import contextmanager
from concurrent.futures import Future as CFuture, TimeoutError

from lenses import Lens

from ribosome.logging import Logging
from ribosome.data import Data
from ribosome.nvim import HasNvim, ScratchBuilder
from ribosome import NvimFacade
from ribosome.machine.message_base import message, Message
from ribosome.machine.base import MachineI, MachineBase
from ribosome.machine.transition import (TransitionResult, Coroutine, may_handle, handle, CoroTransitionResult,
                                         _recover_error, CoroExecutionHandler)
from ribosome.machine.message_base import json_message
from ribosome.machine.helpers import TransitionHelpers
from ribosome.machine.messages import Nop, Done, Quit, PlugCommand, Stop, Error, UpdateRecord, UpdateState
from ribosome.machine.handler import DynHandlerJob
from ribosome.machine.modular import ModularMachine, ModularMachine2
from ribosome.machine.transitions import Transitions
from ribosome.machine import trans
from ribosome.settings import PluginSettings, Config, AutoData
from ribosome.record import field

import amino
from amino import Maybe, Map, Try, _, L, __, Just, Either, List, Left, Nothing, do, Lists, Right, Nil
from amino.util.string import red, blue
from amino.state import State

Callback = message('Callback', 'func')
Envelope = message('Envelope', 'message', 'to')
RunMachine = json_message('RunMachine', 'machine')
KillMachine = message('KillMachine', 'uuid')
RunScratchMachine = json_message('RunScratchMachine', 'machine')
Init = message('Init')
IfUnhandled = message('IfUnhandled', 'msg', 'unhandled')

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


class AsyncIOThread(threading.Thread, AsyncIOBase):

    def __init__(self) -> None:
        threading.Thread.__init__(self)
        AsyncIOBase.__init__(self)
        self.done = threading.Event()
        self.quit_now = threading.Event()
        self.running = threading.Event()

    def run(self):
        self._init_asyncio()
        asyncio.set_event_loop(self._loop)
        self.quit_now.clear()
        self.done.clear()
        self.running.set()
        try:
            self._loop.run_until_complete(self._main(self.init))
            self.log.debug('event loop finished in {}'.format(self.title))
        except Exception:
            self.log.exception('while running state machine')
        self.running.clear()
        self.done.set()

    def stop(self, shutdown=True):
        if self.is_alive() and self.running.is_set():
            self.log.debug('stopping machine {}'.format(self.title))
            if shutdown:
                self._stop()
            else:
                self._done()
            self.send(Nop())
            if self.done.wait(long_timeout):
                try:
                    self._loop.close()
                except Exception as e:
                    if amino.development:
                        self.log.caught_exception('stopping {}'.format(self.title))

    def _stop(self):
        self._done()

    def _done(self):
        self.quit_now.set()

    @abc.abstractmethod
    async def _main(self, initial):
        ...

    @property
    def init(self):
        pass


class StateMachineBase(ModularMachine):

    def __init__(self, sub: List[MachineBase]=List(), parent=None, title=None, debug=False) -> None:
        self.sub = sub
        self.debug = debug
        self.data = None
        self._messages: asyncio.PriorityQueue = None
        self.message_log = List()
        ModularMachine.__init__(self, parent, title=None)

    @property
    def init(self) -> Data:
        return self._data_type()

    def start_wait(self):
        self.start()
        self.wait_for_running()

    def _stop(self):
        self.send(Stop())

    def _publish(self, msg):
        return self._messages.put(msg)

    def send(self, msg: Message, prio=0.5):
        if self._messages is not None:
            return asyncio.run_coroutine_threadsafe(self._messages.put(msg), self._loop)

    def send_sync(self, msg: Message, wait=None):
        self.send(msg)
        return self.await_state(wait)

    def await_state(self, wait=None):
        (asyncio.run_coroutine_threadsafe(self.join_messages(), self._loop)
         .result(Maybe(wait) | short_timeout))
        return self.data

    def eval_expr(self, expr: str, pre: Callable=lambda a, b: (a, b)):
        sub = self.sub
        sub_map = Map(sub / (lambda a: (a.title, a)))
        data, plugins = pre(self.data, sub_map)
        return Try(eval, expr, None, dict(data=data, plugins=plugins))

    def _send(self, data, msg: Message):
        self.log_message(msg, self.title)
        return (
            Try(self.loop_process, data, msg)
            .value_or(L(TransitionResult.failed)(data, _))
        )

    def log_message(self, msg: Message, name: str) -> None:
        self.log.debug('processing {} in {}'.format(msg, name))
        if self.debug:
            self.message_log.append(msg)

    @may_handle(Nop)
    def _nop(self, data: Data, msg):
        pass

    @may_handle(Stop)
    def _stop_msg(self, data: Data, msg):
        return Quit(), Done().pub.at(1)

    @may_handle(Done)
    def _done_msg(self, data: Data, msg):
        self._done()

    @may_handle(Callback)
    def message_callback(self, data: Data, msg):
        return msg.func(data)

    @may_handle(Coroutine)
    def _couroutine(self, data: Data, msg):
        return msg

    @may_handle(RunMachine)
    def _run_machine(self, data, msg):
        self.sub = self.sub.cat(msg.machine)
        init = msg.options.get('init') | Init()
        return Envelope(init, msg.machine.uuid)

    @may_handle(KillMachine)
    def _kill_machine(self, data, msg):
        self.sub = self.sub.filter_not(_.uuid == msg.uuid)

    @handle(Envelope)
    def message_envelope(self, data, msg):
        return self.sub.find(_.uuid == msg.to) / __.loop_process(data, msg.message)

    @may_handle(IfUnhandled)
    def if_unhandled(self, data, msg):
        result = self._send(data, msg.msg)
        return result if result.handled else self._send(data, msg.unhandled)

    def unhandled(self, data, msg):
        prios = (self.sub // _.prios).distinct.sort(reverse=True)
        step = lambda z, a: z if z.handled else self._fold_sub(z.data, msg, a)
        return Just(prios.fold_left(TransitionResult.unhandled(data))(step))

    def _fold_sub(self, data, msg, prio=None):
        ''' send **msg** to all sub-machines, passing the transformed
        data from each machine to the next and accumulating published
        messages.
        '''
        send = lambda z, s: z.accum(s.loop_process(z.data, msg, prio))
        return self.sub.fold_left(TransitionResult.unhandled(data))(send)

    @contextmanager
    def transient(self):
        self.start()
        self.wait_for_running()
        self.send(Nop())
        yield self
        self.stop()

    async def _step(self):
        self.data = await self._process_one_message(self.data)

    async def _process_one_message(self, data):
        msg = await self._messages.get()
        sent = self._send(data, msg)
        result = (
            self._failed_transition(msg, sent)
            if sent.failure else
            await self._successful_transition(data, msg, sent)
            if sent.handled else
            self._unhandled_message(msg, sent)
        )
        self._messages.task_done()
        return result.data

    async def _successful_transition(self, data, msg, sent):
        result = (
            await self._execute_coro_result(data, msg, sent)
            if isinstance(sent, CoroTransitionResult) else
            sent
        )
        for pub in result.pub:
            await self._publish(pub)
        return result

    async def _execute_coro_result(self, data: Data, msg: Message, ctr: CoroTransitionResult) -> None:
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

    def _failed_transition(self, msg, sent: TransitionResult):
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

    def _unhandled_message(self, msg, sent):
        log = self.log.warning if warn_no_handler else self.log.debug
        log('{}: no handler for {}'.format(self.title, msg))
        return sent

    async def join_messages(self):
        await self._messages.join()


class StateMachine(StateMachineBase, AsyncIOThread):

    def __init__(self, *a, **kw) -> None:
        AsyncIOThread.__init__(self)
        StateMachineBase.__init__(self, *a, **kw)

    def wait_for_running(self) -> None:
        self.running.wait(medium_timeout)

    async def _main(self, data):
        self.data = data
        while not self.quit_now.is_set():
            await self._step()


class UnloopedStateMachine(StateMachineBase, AsyncIOBase):

    def __init__(self, *a, **kw) -> None:
        StateMachineBase.__init__(self, *a, **kw)
        AsyncIOBase.__init__(self)

    def start(self) -> None:
        self.data = self.init
        self._init_asyncio()

    def stop(self, shutdown=True) -> None:
        pass

    def wait_for_running(self) -> None:
        pass

    def process_messages(self):
        return self._loop.run_until_complete(self._process_messages())

    async def _process_messages(self):
        while not self._messages.empty():
            await self._step()

    def run_coro_when_free(self, coro: Awaitable) -> None:
        while self._loop.is_running():
            time.sleep(.01)
        self._loop.run_until_complete(coro)

    async def send_and_process(self, msg: Message) -> None:
        if self._messages is not None:
            await self._messages.put(msg)
            await self._process_messages()

    def send_thread(self, msg: Message, asy: bool) -> None:
        a = 'a' if asy else ''
        desc = f'send {msg} {a}sync in {self.title}'
        self.log.debug(desc)
        done = CFuture()
        def run() -> None:
            try:
                self.run_coro_when_free(self.send_and_process(msg))
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
            self.log.warn(f'timed out waiting for processing of {msg} in {self.title}')

    def send(self, msg: Message) -> CFuture:
        return self.send_thread(msg, True)


class PluginStateMachine(MachineI):

    def __init__(self, plugins: List[str]) -> None:
        self.sub = plugins.flat_map(self.start_plugin)

    def start_plugin(self, name: str):
        def report(errs):
            msg = 'invalid {} plugin module "{}": {}'
            self.log.error(msg.format(self.title, name, errs))
        return (self._find_plugin(name) // self._inst_plugin).o(lambda: self.extra_plugin(name)).leffect(report)

    def _find_plugin(self, name: str):
        mods = List(
            Either.import_module(name),
            Either.import_module('{}.plugins.{}'.format(self.title, name))
        )
        # TODO .traverse(_.swap).swap
        errors = mods.filter(_.is_left) / _.value
        return mods.find(_.is_right) | Left(errors)

    def _inst_plugin(self, mod):
        return (
            Try(getattr(mod, 'Plugin'), self.vim, self)
            if hasattr(mod, 'Plugin')
            else Left('module does not define class `Plugin`')
        )

    def extra_plugin(self, name: str) -> Either[str, MachineI]:
        return Left('not implemented')

    def plugin(self, title: str) -> Maybe[MachineBase]:
        return self.sub.find(_.title == title)

    def plug_command(self, plug_name: str, cmd_name: str, args: tuple=(), sync=False):
        sender = self.send_sync if sync else self.send
        plug = self.plugin(plug_name)
        cmd = plug.flat_map(lambda a: a.command(cmd_name, Lists.wrap(args)))
        plug.ap2(cmd, PlugCommand) % sender

    def plug_command_sync(self, *a, **kw):
        return self.plug_command(*a, sync=True, **kw)

    @may_handle(PlugCommand)
    def _plug_command(self, data, msg):
        self.log.debug('sending command {} to plugin {}'.format(msg.msg, msg.plug.title))
        self.log_message(msg.msg, self.title)
        return msg.plug.process(data, msg.msg)


# FIXME why is the title param ignored?
class RootMachineBase(PluginStateMachine, HasNvim, Logging):

    def __init__(self, vim: NvimFacade, plugins: List[str]=List(), title: str=None) -> None:
        HasNvim.__init__(self, vim)
        PluginStateMachine.__init__(self, plugins)

    @property
    def title(self):
        return 'ribosome'

    @handle(RunScratchMachine)
    def _scratch_machine(self, data, msg):
        return (
            ScratchBuilder(**(msg.options - 'init'))
            .build
            .unsafe_perform_io(self.vim) /
            L(msg.machine)(_, self) /
            L(RunMachine)(_, msg.options)
        )


class RootMachine(StateMachine, RootMachineBase):

    def __init__(self, vim: NvimFacade, plugins: List[str]=List(), title: str=Optional[None]) -> None:
        StateMachine.__init__(self, title=title)
        RootMachineBase.__init__(self, vim, plugins)


T = TypeVar('T', bound=Transitions)


class SubMachine2(Generic[T], ModularMachine2[T], TransitionHelpers):

    def __init__(self, vim: NvimFacade, trans: Type[T], parent: Optional[MachineI]=None, title: Optional[str]=None
                 ) -> None:
        super().__init__(parent, title)
        self.vim = vim
        self.trans = trans

    @property
    def transitions(self) -> Type[T]:
        return self.trans

    def new_state(self):
        pass


class UnloopedRootMachine(UnloopedStateMachine, RootMachineBase):

    def __init__(self, vim: NvimFacade, plugins: List[str]=List(), title: str=Optional[None]) -> None:
        debug = vim.vars.p('debug') | False
        UnloopedStateMachine.__init__(self, title=title, debug=debug)
        RootMachineBase.__init__(self, vim, plugins)


Settings = TypeVar('Settings', bound=PluginSettings)
D = TypeVar('D', bound=AutoData)


class AutoRootMachine(Generic[Settings, D], UnloopedRootMachine):

    def __init__(self, vim: NvimFacade, config: Config[Settings, D], title: str) -> None:
        self.config = config
        self.available_plugins = self.config.plugins
        active_plugins = config.settings.components.value.attempt(vim).join | config.default_components
        UnloopedRootMachine.__init__(self, vim, active_plugins, title)

    def extra_plugin(self, name: str) -> Either[str, MachineI]:
        return (
            self.available_plugins
            .lift(name)
            .to_either(f'no auto plugin defined for`{name}`')
            .flat_map(self.inst_auto)
        )

    def inst_auto(self, plug: Union[str, Type]) -> Either[str, MachineI]:
        return (
            Right(SubMachine2(self.vim, plug))
            if isinstance(plug, type) and issubclass(plug, Transitions) else
            Left(f'invalid tpe for auto plugin: {plug}')
        )

    @property
    def init(self) -> D:
        return self.config.state_type(config=self.config, vim_facade=Just(self.vim))


class SubMachine(ModularMachine, TransitionHelpers):

    def new_state(self):
        pass


class SubTransitions(Transitions, TransitionHelpers):

    def _state(self, data):
        return data.sub_state(self.name, self.new_state)

    @property
    def state(self):
        return self._state(self.data)

    def _with_sub(self, data, state):
        return data.with_sub_state(self.name, state)

    def with_sub(self, state):
        return self._with_sub(self.data, state)

    @property
    def new_state(self):
        return self.machine.new_state

    @property
    def options(self):
        return getattr(self.msg, 'options', Map())

    @handle(UpdateRecord)
    def message_update_record(self):
        return (
            self.record_lens(self.msg.tpe, self.msg.name) /
            __.modify(__.update_from_opt(self.msg.options)) /
            self.with_sub
        )

    def record_lens(self, tpe, name) -> Maybe[Lens]:
        return Nothing

    @trans.unit(UpdateState, trans.st)
    @do
    def message_update_state(self) -> Generator[State[Data, None], Any, State[Data, None]]:
        mod = __.update_from_opt(self.msg.options)
        l = yield self.state_lens(self.msg.tpe, self.msg.name)
        yield State.modify(lambda s: l.map(__.modify(mod)) | s)

    def state_lens(self, tpe: str, name: str) -> State[Data, Maybe[Lens]]:
        return State.pure(Nothing)

__all__ = ('StateMachine', 'PluginStateMachine', 'AsyncIOThread', 'StateMachineBase', 'UnloopedStateMachine',
           'PluginStateMachine', 'RootMachineBase', 'RootMachine', 'UnloopedRootMachine', 'SubMachine',
           'SubTransitions')
