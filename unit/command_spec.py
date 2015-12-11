import sure  # NOQA
from flexmock import flexmock  # NOQA

from tek import Spec  # type: ignore

from trypnv.cmd import Command, command

from tryp import Just


class Command_(Spec, ):

    def name(self):
        def cmd_name(a, b, c=2):
            pass
        Command(cmd_name).name.should.equal('CmdName')
        other_name = 'OtherName'
        Command(cmd_name, other_name).name.should.equal(other_name)

    def nargs(self):
        def none():
            pass

        def one(a):
            pass

        def two(a, b):
            pass

        def two_default(a, b=1):
            pass

        def more(a, b, c, d=1, *va, **vkw):
            pass

        def check(fun, nargs, spec):
            c = Command(fun)
            c.nargs.should.equal(nargs)
            c.count_spec.should.equal(spec)

        check(none, 0, 'none')
        check(one, 1, 'exactly 1')
        check(two, '+', 'exactly 2')
        check(two_default, '+', 'between 1 and 2')
        check(more, '+', 'at least 3')

    def none(self):
        def fun():
            pass
        c = Command(fun)
        c.min.should.equal(0)
        c.max.should.equal(Just(0))
        c.check_length([]).should.be.ok
        c.check_length([1]).should_not.be.ok

    def one(self):
        def fun(a):
            pass
        c = Command(fun)
        c.min.should.equal(1)
        c.max.should.equal(Just(1))
        c.check_length([]).should_not.be.ok
        c.check_length([1]).should.be.ok
        c.check_length([1, 2]).should_not.be.ok

    def one_opt(self):
        def fun(a=1):
            pass
        c = Command(fun)
        c.min.should.equal(0)
        c.max.should.equal(Just(1))
        c.check_length([]).should.be.ok
        c.check_length([1]).should.be.ok
        c.check_length([1, 2]).should_not.be.ok

    def two(self):
        def fun(a, b):
            pass
        c = Command(fun)
        c.min.should.equal(2)
        c.max.should.equal(Just(2))
        c.check_length([]).should_not.be.ok
        c.check_length([1]).should_not.be.ok
        c.check_length([1, 2]).should.be.ok
        c.check_length([1, 2, 3]).should_not.be.ok

    def two_one_opt(self):
        def fun(a, b=1):
            pass
        c = Command(fun)
        c.min.should.equal(1)
        c.max.should.equal(Just(2))
        c.check_length([]).should_not.be.ok
        c.check_length([1]).should.be.ok
        c.check_length([1, 2]).should.be.ok
        c.check_length([1, 2, 3]).should_not.be.ok

    def two_opt(self):
        def fun(a=1, b=1):
            pass
        c = Command(fun)
        c.min.should.equal(0)
        c.max.should.equal(Just(2))
        c.check_length([]).should.be.ok
        c.check_length([1]).should.be.ok
        c.check_length([1, 2]).should.be.ok
        c.check_length([1, 2, 3]).should_not.be.ok

    def six(self):
        def fun(a, b, c, d, e, f):
            pass
        c = Command(fun)
        c.min.should.equal(6)
        c.max.should.equal(Just(6))
        c.check_length([]).should_not.be.ok
        c.check_length([1]).should_not.be.ok
        c.check_length([1, 2, 3, 4, 5, 6]).should.be.ok
        c.check_length([1, 2, 3, 4, 5, 6, 7]).should_not.be.ok

    def var(self):
        def fun(a, b=1, *args):
            pass
        c = Command(fun)
        c.min.should.equal(1)
        c.max.isJust.should_not.be.ok
        c.check_length([]).should_not.be.ok
        c.check_length([1]).should.be.ok
        c.check_length([1, 2]).should.be.ok
        c.check_length([1, 2, 3]).should.be.ok

    def decorator(self):
        default = 1

        class Cmd(object):
            @command()
            def cmd_name(self, a=default):
                return a

        c = Cmd()

        def wrap(args):
            return c.cmd_name(args)
        wrap.when.called_with([]).should.return_value(default)
        val = 2
        wrap.when.called_with([val]).should.return_value(val)
        wrap([1, 2]).endswith('between 0 and 1 ([1, 2])').should.be.ok

__all__ = ['Command_']
