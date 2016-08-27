import neovim

from ribosome import command, NvimStatePlugin

from amino.lazy import lazy
from ribosome.logging import Logging
from ribosome.request import function, msg_function
from ribosome.machine import message, may_handle
from ribosome.machine.state import RootMachine


Msg = message('Msg', 'text')


class Mach(RootMachine):

    @may_handle(Msg)
    def mess(self, data, msg):
        self.log.info(msg.text)


class TestPlugin(NvimStatePlugin, Logging):
    test_go = 'TestPlugin cmd test message'
    test_fun = 'TestPlugin fun test message'
    test_value = 'test value {}'

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

__all__ = ('TestPlugin',)
