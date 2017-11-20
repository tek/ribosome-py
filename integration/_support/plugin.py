import asyncio
import time

import neovim

from ribosome import command, NvimStatePlugin, msg_function, msg_command, function

from amino import Left, L, _, Map, List, Just, Lists, IO
from amino.state import EvalState
from ribosome.logging import Logging
from ribosome.nvim import NvimFacade, ScratchBuffer
from ribosome.data import Data
from ribosome.record import int_field
from ribosome.trans.message_base import pmessage, Message
from ribosome.trans.messages import Nop, RunCorosParallel, RunIOsParallel
from ribosome.trans.legacy import Fatal
from ribosome.components.scratch import Mapping, Scratch
from ribosome.trans.api import trans


Msg1 = pmessage('Msg1', 'text')
Err = pmessage('Err')
ScratchMsg = pmessage('ScratchMsg')
ScratchTest = pmessage('ScratchTest')
ScratchCheck = pmessage('ScratchCheck')
St = pmessage('St')
Print = pmessage('Print', 'msg')
RunParallel = pmessage('RunParallel')
RunParallelIOs = pmessage('RunParallelIOs')


class TData(Data):
    v = int_field(initial=0)

    @property
    def _str_extra(self) -> List[str]:
        return List(self.v)


class Mach(Logging):

    @trans.msg.one(Msg1)
    def mess(self, data, msg):
        self.log.info(msg.text)
        return data.set(v=3)

    @trans.msg.unit(Err)
    def err(self, data, msg):
        return Left(Fatal(TestPlugin.test_error))

    @trans.msg.one(ScratchMsg)
    def run_scratch(self, data, msg):
        ctor = L(ScratchM)(self.vim, _, _)
        return RunScratchMachine(ctor)

    @trans.msg.one(ScratchCheck)
    def check_scratch(self, data, msg):
        self.log.info(self.sub.length)

    @trans.msg.one(St)
    def st(self, data, msg) -> EvalState[TData, Message]:
        return EvalState.inspect(lambda a: Just(Print(a.v * 2)))

    @trans.msg.one(Print)
    def print_(self, data: Data, msg: Print) -> Message:
        self.log.info(msg.msg)

    @trans.msg.one(RunParallel)
    def run_parallel(self, data: Data, msg: RunParallel) -> Message:
        async def go(n: int) -> None:
            self.log.info(f'sleeping in {n}')
            await asyncio.sleep(.1)
            return Nop().pub
        coros = Lists.range(3) / go
        return RunCorosParallel(coros)

    @trans.msg.one(RunParallelIOs)
    def run_parallel_ios(self, data: Data, msg: RunParallelIOs) -> Message:
        def go(n: int) -> None:
            self.log.info(f'sleeping in {n}')
            time.sleep(.1)
            return Nop().pub
        ios = Lists.range(3) / L(IO.delay)(go, _)
        return RunIOsParallel(ios)


class MachLooped(Mach, RootMachine):
    _data_type = TData


class MachUnlooped(Mach, UnloopedRootMachine):
    _data_type = TData


class ScratchM(Scratch):

    def __init__(self, vim: NvimFacade, scratch: ScratchBuffer) -> None:
        super().__init__(vim, scratch, name='scratch')

    @property
    def prefix(self):
        return 'Test'

    @property
    def mappings(self):
        return Map()

    @may_fallback(ScratchTest)
    def test(self, data, msg):
        self.log.info(TestPlugin.test_scratch)


class TestPlugin(NvimStatePlugin, Logging):
    test_go = 'TestPlugin cmd test message'
    test_fun = 'TestPlugin fun test message'
    test_value = 'test value {}'
    test_error = 'test error'
    test_scratch = 'test scratch'

    def start_plugin(self) -> None:
        self.state().start()

    @neovim.function('Value', sync=True)
    def value(self, args):
        return self.test_value.format(args[0])

    @command(sync=True)
    def go(self):
        self.start_plugin()
        self.log.info(self.test_go)

    @function()
    def fun(self, value):
        return self.test_fun.format(value)

    @msg_function(Msg1, sync=True)
    def msg_fun(self):
        pass

    @msg_command(Err)
    def err(self):
        pass

    @msg_command(St)
    def st(self):
        pass

    @msg_command(ScratchMsg)
    def scratch(self):
        pass

    @msg_command(ScratchTest)
    def scratch_test(self):
        pass

    @msg_function(Mapping)
    def test_mapping(self):
        pass

    @msg_command(ScratchCheck)
    def check_scratch(self):
        pass

    @msg_command(RunParallel)
    def run_parallel(self) -> None:
        pass

    @msg_command(RunParallelIOs)
    def run_parallel_i_os(self) -> None:
        pass


class TestPluginLooped(TestPlugin):

    def __init__(self, vim) -> None:
        super().__init__(vim)
        self._state = None

    def state(self) -> MachLooped:
        if self._state is None:
            self._state = MachLooped(self.vim.proxy, name='spec')
        return self._state


class TestPluginUnlooped(TestPlugin):

    def __init__(self, vim) -> None:
        super().__init__(vim)
        self._state = None

    def state(self) -> MachLooped:
        if self._state is None:
            self._state = MachUnlooped(self.vim.proxy, name='spec')
        return self._state

__all__ = ('TestPlugin',)
