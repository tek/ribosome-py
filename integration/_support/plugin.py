import neovim

from ribosome import command, NvimStatePlugin

from amino.lazy import lazy
from amino import Left
from ribosome.logging import Logging
from ribosome.request import function, msg_function, msg_command
from ribosome.machine import message, may_handle, handle
from ribosome.machine.state import RootMachine


Msg = message('Msg', 'text')
Err = message('Err')


class Mach(RootMachine):

    @may_handle(Msg)
    def mess(self, data, msg):
        self.log.info(msg.text)

    @handle(Err)
    def err(self, data, msg):
        return Left(TestPlugin.test_error)


class TestPlugin(NvimStatePlugin, Logging):
    test_go = 'TestPlugin cmd test message'
    test_fun = 'TestPlugin fun test message'
    test_value = 'test value {}'
    test_error = 'test error'

    def start(self):
        self.state.start()

    @lazy
    def state(self):
        return Mach(self, title='spec')

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

__all__ = ('TestPlugin',)
