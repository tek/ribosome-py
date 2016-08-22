from typing import Callable
import abc
import threading
import asyncio
from concurrent import futures
import importlib
from contextlib import contextmanager

from ribosome.logging import Logging
from ribosome.data import Data
from ribosome.nvim import HasNvim
from ribosome import NvimFacade
from ribosome.machine.message_base import (message, Message, Nop, Done, Quit,
                                           PlugCommand, Stop)
from ribosome.machine.base import ModularMachine, Machine, may_handle
from ribosome.machine.transition import (TransitionResult, Coroutine,
                                         TransitionFailed)

from amino import Maybe, List, Map, may, Try, _
from amino.tc.optional import Optional  # NOQA

Callback = message('Callback', 'func')
IO = message('IO', 'perform')
Info = message('Info', 'message')


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
            try:
                self.done.result(5)
            except Exception as e:
                self.log.error(e)
            finally:
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
        asyncio.run_coroutine_threadsafe(self.join_messages(),
                                         self._loop).result(2)
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

    async def join_messages(self):
        await self._messages.join()


class PluginStateMachine(StateMachine):

    def __init__(self, plugins: List[str], title=None) -> None:
        StateMachine.__init__(self, title=title)
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

    def __init__(self, vim: NvimFacade, plugins: List[str]=List(), title=None
                 ) -> None:
        HasNvim.__init__(self, vim)
        PluginStateMachine.__init__(self, plugins, title=None)

    @property
    def title(self):
        return 'ribosome'

__all__ = ('Machine', 'Message', 'StateMachine', 'PluginStateMachine', 'Info')
