from ribosome.request import command

from unit._support.spec import Spec


class CommandSpec(Spec):

    def decorator(self):
        default = 1
        class Cmd(object):
            @command()
            def cmd_name(self, a=default):
                return a
        c = Cmd()
        def wrap(args):
            return c.cmd_name(args)
        wrap([]).should.equal(default)
        val = 2
        wrap([val]).should.equal(val)
        wrap([1, 2]).endswith('between 0 and 1 ([1, 2])').should.be.ok

__all__ = ('CommandSpec',)
