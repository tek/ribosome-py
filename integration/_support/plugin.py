import neovim

from ribosome import command, NvimStatePlugin

from amino.lazy import lazy
from amino import Left, L, _, Map, List, Eval, Task, Just
from amino.state import State
from ribosome.logging import Logging
from ribosome.request import function, msg_function, msg_command
from ribosome.machine import message, may_handle, handle, Machine, Message, Nop
from ribosome.machine.state import (UnloopedRootMachine, RunScratchMachine,
                                    RootMachine)
from ribosome.machine.transition import Fatal, may_fallback
from ribosome.machine.scratch import ScratchMachine, Mapping
from ribosome.nvim import NvimFacade, ScratchBuffer
from ribosome.data import Data
from ribosome.record import int_field


Msg = message('Msg', 'text')
Err = message('Err')
Scratch = message('Scratch')
ScratchTest = message('ScratchTest')
ScratchCheck = message('ScratchCheck')
St = message('St')
Print = message('Print', 'msg')


class TData(Data):
    v = int_field(initial=0)

    @property
    def _str_extra(self) -> List[str]:
        return List(self.v)


class Mach(Logging):

    @may_handle(Msg)
    def mess(self, data, msg):
        self.log.info(msg.text)
        return data.set(v=3)

    @handle(Err)
    def err(self, data, msg):
        return Left(Fatal(TestPlugin.test_error))

    @may_handle(Scratch)
    def run_scratch(self, data, msg):
        ctor = L(ScratchM)(self.vim, _, _)
        return RunScratchMachine(ctor)

    @may_handle(ScratchCheck)
    def check_scratch(self, data, msg):
        self.log.info(self.sub.length)

    @may_handle(St)
    def st(self, data, msg) -> State[TData, Message]:
        return State.inspect(lambda a: Just(Print(a.v * 2)), Eval)

    @may_handle(Print)
    def print_(self, data: Data, msg: Print) -> Message:
        self.log.info(msg.msg)


class MachLooped(Mach, RootMachine):
    _data_type = TData


class MachUnlooped(Mach, UnloopedRootMachine):
    pass


class ScratchM(ScratchMachine):

    def __init__(self, vim: NvimFacade, scratch: ScratchBuffer,
                 parent: Machine) -> None:
        super().__init__(vim, scratch, parent=parent, title='scratch')

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

    def start(self):
        self.state.start()

    @neovim.function('Value', sync=True)
    def value(self, args):
        return self.test_value.format(args[0])

    @command(sync=True)
    def go(self):
        self.start()
        self.log.info(self.test_go)

    @function()
    def fun(self, value):
        return self.test_fun.format(value)

    @msg_function(Msg, sync=True)
    def msg_fun(self):
        pass

    @msg_command(Err)
    def err(self):
        pass

    @msg_command(St)
    def st(self):
        pass

    @msg_command(Scratch)
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


class TestPluginLooped(TestPlugin):

    @lazy
    def state(self):
        return MachLooped(self.vim.proxy, title='spec')


class TestPluginUnlooped(TestPlugin):

    @lazy
    def state(self):
        return MachUnlooped(self.vim.proxy, title='spec')

__all__ = ('TestPlugin',)
