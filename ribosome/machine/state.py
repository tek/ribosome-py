import time
from typing import Callable, Awaitable, Generator, Any, Union, TypeVar, Generic, Type, Optional
import abc
import threading
import asyncio
from contextlib import contextmanager
from concurrent.futures import Future as CFuture, TimeoutError
import subprocess
from subprocess import PIPE

from lenses import Lens

from ribosome.logging import Logging
from ribosome.data import Data
from ribosome.nvim import HasNvim, ScratchBuilder
from ribosome import NvimFacade
from ribosome.machine.message_base import message, Message
from ribosome.machine.base import Machine, MachineBase
from ribosome.machine.transition import (TransitionResult, Coroutine, may_handle, handle, CoroTransitionResult,
                                         _recover_error, CoroExecutionHandler)
from ribosome.machine.message_base import json_message
from ribosome.machine.helpers import TransitionHelpers
from ribosome.machine.messages import (Nop, Done, Quit, PlugCommand, Stop, Error, UpdateRecord, UpdateState,
                                       CoroutineAlg, SubProcessAsync, Fork)
from ribosome.machine.handler import DynHandlerJob, AlgResultValidator
from ribosome.machine.modular import ModularMachine, ModularMachine2
from ribosome.machine.transitions import Transitions
from ribosome.machine import trans
from ribosome.settings import PluginSettings, Config, AutoData

import amino
from amino import Maybe, Map, Try, _, L, __, Just, Either, List, Left, Nothing, do, Lists, Right, curried, Boolean, Nil
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
            self.log.debug('event loop finished in {}'.format(self.name))
        except Exception:
            self.log.exception('while running state machine')
        self.running.clear()
        self.done.set()

    def stop(self, shutdown=True):
        if self.is_alive() and self.running.is_set():
            self.log.debug('stopping machine {}'.format(self.name))
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
                        self.log.caught_exception('stopping {}'.format(self.name))

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

    def __init__(self, sub: List[MachineBase]=List(), parent=None, name=None, debug=False) -> None:
        self.sub = sub
        self.debug = debug
        self.data = None
        self._messages: asyncio.PriorityQueue = None
        self.message_log = List()
        ModularMachine.__init__(self, parent, name=name)

    @property
    def init(self) -> Data:
        return self._data_type()

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

    def _send(self, data, msg: Message):
        self.log_message(msg, self.name)
        return (
            Try(self.loop_process, data, msg)
            .value_or(L(TransitionResult.failed)(data, _))
        )

    def log_message(self, msg: Message, name: str) -> None:
        self.append_message_log(msg, name)

    def append_message_log(self, msg: Message, name: str) -> None:
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

    @may_handle(CoroutineAlg)
    def message_couroutine_alg(self, data: Data, msg: CoroutineAlg):
        async def run_coro_alg() -> None:
            res = await msg.coro
            trans_desc = blue(f'{self.name}.message_couroutine_alg')
            return Just(AlgResultValidator(trans_desc).validate(res, data))
        return run_coro_alg()

    @trans.one(SubProcessAsync)
    def message_sub_process_async(self, data: Data, msg: SubProcessAsync) -> None:
        def subproc_async() -> Message:
            job = msg.job
            proc = subprocess.run(
                executable=job.exe,
                args=job.args,
                stdin=PIPE,
                stdout=PIPE,
                stderr=PIPE,
                cwd=str(job.cwd),
                **job.kw,
            )
            return Nil
        return Fork(subproc_async)

    @trans.unit(Fork)
    def message_fork(self, data: Data, msg: Fork) -> None:
        def dispatch() -> None:
            try:
                msg.callback() % self._messages.put_nowait
            except Exception as e:
                self.log.caught_exception(f'running forked function {msg.callback}', e)
        threading.Thread(target=dispatch).start()

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
        log(f'no handler for {msg}')
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
        self.log.debug(f'starting event loop in {self}')
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

    def send_and_process(self, msg: Message) -> None:
        if self._messages is not None:
            self._messages.put_nowait(msg)
            if not self._loop.is_running():
                try:
                    self._loop.run_until_complete(self._process_messages())
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
                self.send_and_process(msg)
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
        return self.send_thread(msg, True)


class PluginStateMachine(Machine):

    def __init__(self, components: List[str]) -> None:
        self.sub = components.flat_map(self.start_components)

    def start_components(self, name: str):
        def report(errs):
            msg = 'invalid {} component module "{}": {}'
            self.log.error(msg.format(self.name, name, errs))
        return (
            (self._find_component(name) // self._inst_component)
            .lmap(List)
            .accum_error_f(lambda: self.extra_component(name))
            .leffect(report)
        )

    def _find_component(self, name: str) -> Either[List[str], Machine]:
        mods = List(
            Either.import_module(name),
            Either.import_module(f'{self.name}.components.{name}'),
            Either.import_module(f'{self.name}.plugins.{name}'),
        )
        # TODO .traverse(_.swap).swap
        errors = mods.filter(_.is_left) / _.value
        return mods.find(_.is_right) | Left(errors)

    def _inst_component(self, mod):
        return (
            Try(getattr(mod, 'Component'), self.vim, self)
            if hasattr(mod, 'Component')
            else Left('module does not define class `Component`')
        )

    def extra_component(self, name: str) -> Either[List[str], Machine]:
        return Left(List('not implemented'))

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


class RootMachineBase(PluginStateMachine, HasNvim, Logging):

    def __init__(self, vim: NvimFacade, components: List[str]=List(), name: str=None) -> None:
        HasNvim.__init__(self, vim)
        PluginStateMachine.__init__(self, components)

    @property
    def name(self):
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

    def __init__(self, vim: NvimFacade, components: List[str]=List(), name: str=Optional[None]) -> None:
        StateMachine.__init__(self, name=name)
        RootMachineBase.__init__(self, vim, components)


T = TypeVar('T', bound=Transitions)


class ComponentMachine(Generic[T], ModularMachine2[T], TransitionHelpers):

    def __init__(self, vim: NvimFacade, trans: Type[T], name: Optional[str], parent: Optional[Machine]=None) -> None:
        super().__init__(parent, name)
        self.vim = vim
        self.trans = trans

    @property
    def transitions(self) -> Type[T]:
        return self.trans

    def new_state(self):
        pass


class UnloopedRootMachine(UnloopedStateMachine, RootMachineBase):

    def __init__(self, vim: NvimFacade, components: List[str]=List(), name: Optional[str]=None) -> None:
        debug = vim.vars.p('debug') | False
        UnloopedStateMachine.__init__(self, name=name, debug=debug)
        RootMachineBase.__init__(self, vim, components)


Settings = TypeVar('Settings', bound=PluginSettings)
D = TypeVar('D', bound=AutoData)


class AutoRootMachine(Generic[Settings, D], UnloopedRootMachine):

    def __init__(self, vim: NvimFacade, config: Config[Settings, D], name: str) -> None:
        self.config = config
        self.available_components = config.components
        additional_components = config.settings.components.value.attempt(vim).join | config.default_components
        components = config.core_components + additional_components
        self.log.debug(f'starting {config} with components {components}')
        UnloopedRootMachine.__init__(self, vim, components, name)

    def extra_component(self, name: str) -> Either[List[str], Machine]:
        auto = f'{self.name}.components.{name}'
        return (
            self.declared_component(name)
            .accum_error_f(lambda: self.component_from_exports(auto))
            .accum_error_f(lambda: self.component_from_exports(name))
            .flat_map(self.inst_auto(name))
        )

    def declared_component(self, name: str) -> Either[List[str], Machine]:
        return (
            self.available_components
            .lift(name)
            .to_either(List(f'no auto component defined for `{name}`'))
        )

    @do
    def component_from_exports(self, mod: str) -> Either[List[str], Machine]:
        exports = yield Either.exports(mod).lmap(List)
        yield (
            exports.find(L(Boolean.issubclass)(_, (Component, ComponentMachine)))
            .to_either(f'none of `{mod}.__all__` is a `Component`: {exports}')
            .lmap(List)
        )

    @curried
    def inst_auto(self, name: str, plug: Union[str, Type]) -> Either[str, Machine]:
        return (
            Right(ComponentMachine(self.vim, plug, name, self))
            if isinstance(plug, type) and issubclass(plug, Transitions) else
            Right(plug(self.vim, name, self))
            if isinstance(plug, type) and issubclass(plug, ComponentMachine) else
            Left(List(f'invalid tpe for auto component: {plug}'))
        )

    @property
    def init(self) -> D:
        return self.config.state(self.vim)


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
    def message_update_state(self) -> Generator[State[Data, None], Any, None]:
        mod = __.update_from_opt(self.msg.options)
        l = yield self.state_lens(self.msg.tpe, self.msg.name)
        yield State.modify(lambda s: l.map(__.modify(mod)) | s)

    def state_lens(self, tpe: str, name: str) -> State[Data, Maybe[Lens]]:
        return State.pure(Nothing)


class Component(SubTransitions):
    pass

__all__ = ('StateMachine', 'PluginStateMachine', 'AsyncIOThread', 'StateMachineBase', 'UnloopedStateMachine',
           'RootMachineBase', 'RootMachine', 'UnloopedRootMachine', 'SubMachine', 'SubTransitions', 'Component',
           'ComponentMachine')
