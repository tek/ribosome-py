import neovim

from ribosome import command, NvimStatePlugin

from amino.lazy import lazy
from amino import Left, L, _, Map
from ribosome.logging import Logging
from ribosome.request import function, msg_function, msg_command
from ribosome.machine import message, may_handle, handle, Machine
from ribosome.machine.state import RootMachine, RunScratchMachine
from ribosome.machine.transition import Fatal, may_fallback
from ribosome.machine.scratch import ScratchMachine, Mapping
from ribosome.nvim import NvimFacade, ScratchBuffer


Msg = message('Msg', 'text')
Err = message('Err')
Scratch = message('Scratch')
ScratchTest = message('ScratchTest')
ScratchCheck = message('ScratchCheck')


class Mach(RootMachine):

    @may_handle(Msg)
    def mess(self, data, msg):
        self.log.info(msg.text)

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

    @lazy
    def state(self):
        return Mach(self.vim.proxy, title='spec')

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

    @msg_function(Msg)
    def msg_fun(self):
        pass

    @msg_command(Err)
    def err(self):
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

__all__ = ('TestPlugin',)
