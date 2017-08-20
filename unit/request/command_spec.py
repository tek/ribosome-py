from ribosome.request import command

from kallikrein import kf
from kallikrein.matchers.end_with import end_with


class CommandSpec:
    '''vim command decorator $decorator
    '''

    def decorator(self):
        default = 1
        class Cmd(object):
            @command()
            def cmd_name(self, a=default):
                return a
        c = Cmd()
        def wrap(args):
            return c.cmd_name(args)
        val = 2
        return (
            (kf(wrap, []) == default) &
            (kf(wrap, [val]) == val) &
            (kf(wrap, [1, 2])).must(end_with('between 0 and 1 ([1, 2])'))
        )

__all__ = ('CommandSpec',)
