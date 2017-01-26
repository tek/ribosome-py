from typing import Callable
from typing import Optional  # NOQA
import abc
import threading
import asyncio
from contextlib import contextmanager
import concurrent.futures

from lenses import Lens

from ribosome.logging import Logging
from ribosome.data import Data
from ribosome.nvim import HasNvim, ScratchBuilder
from ribosome import NvimFacade
from ribosome.machine.message_base import (message, Message, Nop, Done, Quit,
                                           PlugCommand, Stop)
from ribosome.machine.base import (ModularMachine, Machine, Transitions,
                                   HandlerJob, MachineBase)
from ribosome.machine.transition import (TransitionResult, Coroutine,
                                         may_handle, handle)
from ribosome.machine.message_base import json_message
from ribosome.machine.helpers import TransitionHelpers

import amino
from amino import Maybe, Map, Try, _, L, __, Empty, Just, Either, List, Left

Callback = message('Callback', 'func')
IO = message('IO', 'perform')
Info = message('Info', 'message')
Envelope = message('Envelope', 'message', 'to')
RunMachine = json_message('RunMachine', 'machine')
KillMachine = message('KillMachine', 'uuid')
RunScratchMachine = json_message('RunScratchMachine', 'machine')
Init = message('Init')
IfUnhandled = message('IfUnhandled', 'msg', 'unhandled')
UpdateRecord = json_message('UpdateRecord', 'tpe', 'name')

short_timeout = 3
medium_timeout = 3
long_timeout = 5
warn_no_handler = True


class AsyncIOBase(Logging, abc.ABC):

    def _init_asyncio(self):
        self._loop = (
            asyncio.new_event_loop()
            if asyncio._get_running_loop() is None  # type: ignore
            else asyncio.get_event_loop()
        )
        self._messages = asyncio.PriorityQueue(loop=self._loop)


class AsyncIOThread(threading.Thread, AsyncIOBase):

    def __init__(self) -> None:
        threading.Thread.__init__(self)
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
                        self.log.caught_exception(
                            'stopping {}'.format(self.title))

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

    def __init__(self, sub: List[Machine]=List(), parent=None, title=None
                 ) -> None:
        self.data = None
        self._messages = None
        self.sub = sub
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
        self.log.debug('send {} in {}'.format(msg, self.title))
        if self._messages is not None:
            return asyncio.run_coroutine_threadsafe(self._messages.put(msg),
                                                    self._loop)

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
        return (
            Try(self.loop_process, data, msg)
            .right_or_map(L(TransitionResult.failed)(data, _))
        )

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
        return self.sub.find(_.uuid == msg.to) / __.loop_process(data,
                                                                 msg.message)

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
            await self._successful_transition(data, msg, sent)
            if sent.handled else
            self._failed_transition(msg, sent)
            if sent.failure else
            self._unhandled_message(msg, sent)
        )
        self._messages.task_done()
        return result.data

    async def _successful_transition(self, data, msg, sent):
        job = HandlerJob(self, data, msg, None, self._data_type)
        result = await sent.await_coro(job.dispatch_transition_result)
        for pub in result.pub:
            await self._publish(pub)
        return result

    def _failed_transition(self, msg, sent):
        errmsg = sent.error_message
        msg_name = type(msg).__name__
        self.log.error('error handling {}: {}'.format(msg_name, errmsg))
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

    def wait_for_running(self):
        self.running.wait(medium_timeout)

    async def _main(self, data):
        self.data = data
        while not self.quit_now.is_set():
            await self._step()


class UnloopedStateMachine(StateMachineBase, AsyncIOBase):

    def start(self):
        self.data = self.init
        self._init_asyncio()

    def wait_for_running(self):
        pass

    def process_messages(self):
        return self._loop.run_until_complete(self._process_messages())

    async def _process_messages(self):
        while not self._messages.empty():
            await self._step()

    def send_sync(self, msg, timeout=medium_timeout):
        self.log.debug('send {} in {}'.format(msg, self.title))
        done = concurrent.futures.Future()  # type: concurrent.futures.Future
        async def go():
            if self._messages is not None:
                await self._messages.put(msg)
            result = await self._process_messages()
            done.set_result(result)
        if self._loop.is_running():
            self._loop.call_soon_threadsafe(go())
        else:
            self._loop.run_until_complete(go())
        return done.result(timeout)

    def send(self, msg):
        threading.Thread(target=self.send_sync, args=(msg,)).start()


class PluginStateMachine(MachineBase):

    def __init__(self, plugins: List[str]) -> None:
        self.sub = plugins.flat_map(self.start_plugin)

    def start_plugin(self, name: str):
        def report(errs):
            msg = 'invalid {} plugin module "{}": {}'
            self.log.error(msg.format(self.title, name, errs))
        return (self._find_plugin(name) // self._inst_plugin).leffect(report)

    def _find_plugin(self, name: str):
        mods = List(
            Either.import_module(name),
            Either.import_module('{}.plugins.{}'.format(self.title, name))
        )
        errors = mods.filter(_.is_left) / _.value
        return mods.find(_.is_right) | Left(errors)

    def _inst_plugin(self, mod):
        return (
            Try(getattr(mod, 'Plugin'), self.vim, self)
            if hasattr(mod, 'Plugin')
            else Left('module does not define class `Plugin`')
        )

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


# FIXME why is the title param ignored?
class RootMachineBase(PluginStateMachine, HasNvim, Logging):

    def __init__(self, vim: NvimFacade, plugins: List[str]=List(), title=None
                 ) -> None:
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

    def __init__(self, vim: NvimFacade, plugins: List[str]=List(), title=None
                 ) -> None:
        StateMachine.__init__(self, title=title)
        RootMachineBase.__init__(self, vim, plugins)


class UnloopedRootMachine(UnloopedStateMachine, RootMachineBase):

    def __init__(self, vim: NvimFacade, plugins: List[str]=List(), title=None
                 ) -> None:
        UnloopedStateMachine.__init__(self, title=title)
        RootMachineBase.__init__(self, vim, plugins)


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
        return Empty()

__all__ = ('Machine', 'Message', 'StateMachine', 'PluginStateMachine', 'Info')
