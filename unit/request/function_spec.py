from ribosome.request import function

from kallikrein import kf
from kallikrein.matchers.end_with import end_with


class FunctionSpec:
    '''vim function decorator $decorator
    '''

    def decorator(self):
        default = 1
        class Fun(object):
            @function()
            def cmd_name(self, a=default):
                return a
        c = Fun()
        def wrap(args):
            return c.cmd_name(args)
        val = 2
        return (
            (kf(wrap, []) == default) &
            (kf(wrap, [val]) == val) &
            (kf(wrap, [1, 2])).must(end_with('between 0 and 1 ([1, 2])'))
        )

__all__ = ('FunctionSpec',)
