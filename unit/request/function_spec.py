from amino.test import Spec

from ribosome.request import function


class FunctionSpec(Spec, ):

    def decorator(self):
        default = 1
        class Fun(object):
            @function()
            def cmd_name(self, a=default):
                return a
        c = Fun()
        def wrap(args):
            return c.cmd_name(args)
        wrap([]).should.equal(default)
        val = 2
        wrap([val]).should.equal(val)
        wrap([1, 2]).endswith('between 0 and 1 ([1, 2])').should.be.ok

__all__ = ('FunctionSpec',)
