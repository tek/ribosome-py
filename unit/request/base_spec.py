import json

from amino import Just
from amino.test import Spec

from ribosome.request.base import (RequestHandler, MessageRequestHandler,
                                   JsonMessageRequestHandler)
from ribosome.machine import message


BasicMessage = message(
    'BasicMessage', 'a', 'b', opt_fields=(('c', 1), ('d', 2)))


JsonMessage = message('JsonMessage', 'a', 'b')


class RH(RequestHandler):

    @property
    def desc(self):
        return 'req_test'


class MessageRH(RH, MessageRequestHandler):
    pass


class JsonMessageRH(RH, JsonMessageRequestHandler):
    pass


class RequestHandlerSpec(Spec):

    def name(self):
        def cmd_name(a, b, c=2):
            pass
        RH(cmd_name).name.should.equal('CmdName')
        other_name = 'OtherName'
        RH(cmd_name, other_name).name.should.equal(other_name)

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
            c = RH(fun)
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
        c = RH(fun)
        c.min.should.equal(0)
        c.max.should.equal(Just(0))
        c.check_length([]).should.be.ok
        c.check_length([1]).should_not.be.ok

    def one(self):
        def fun(a):
            pass
        c = RH(fun)
        c.min.should.equal(1)
        c.max.should.equal(Just(1))
        c.check_length([]).should_not.be.ok
        c.check_length([1]).should.be.ok
        c.check_length([1, 2]).should_not.be.ok

    def one_opt(self):
        def fun(a=1):
            pass
        c = RH(fun)
        c.min.should.equal(0)
        c.max.should.equal(Just(1))
        c.check_length([]).should.be.ok
        c.check_length([1]).should.be.ok
        c.check_length([1, 2]).should_not.be.ok

    def two(self):
        def fun(a, b):
            pass
        c = RH(fun)
        c.min.should.equal(2)
        c.max.should.equal(Just(2))
        c.check_length([]).should_not.be.ok
        c.check_length([1]).should_not.be.ok
        c.check_length([1, 2]).should.be.ok
        c.check_length([1, 2, 3]).should_not.be.ok

    def two_one_opt(self):
        def fun(a, b=1):
            pass
        c = RH(fun)
        c.min.should.equal(1)
        c.max.should.equal(Just(2))
        c.check_length([]).should_not.be.ok
        c.check_length([1]).should.be.ok
        c.check_length([1, 2]).should.be.ok
        c.check_length([1, 2, 3]).should_not.be.ok

    def two_opt(self):
        def fun(a=1, b=1):
            pass
        c = RH(fun)
        c.min.should.equal(0)
        c.max.should.equal(Just(2))
        c.check_length([]).should.be.ok
        c.check_length([1]).should.be.ok
        c.check_length([1, 2]).should.be.ok
        c.check_length([1, 2, 3]).should_not.be.ok

    def six(self):
        def fun(a, b, c, d, e, f):
            pass
        c = RH(fun)
        c.min.should.equal(6)
        c.max.should.equal(Just(6))
        c.check_length([]).should_not.be.ok
        c.check_length([1]).should_not.be.ok
        c.check_length([1, 2, 3, 4, 5, 6]).should.be.ok
        c.check_length([1, 2, 3, 4, 5, 6, 7]).should_not.be.ok

    def var(self):
        def fun(a, b=1, *args):
            pass
        c = RH(fun)
        c.min.should.equal(1)
        c.max.is_just.should_not.be.ok
        c.check_length([]).should_not.be.ok
        c.check_length([1]).should.be.ok
        c.check_length([1, 2]).should.be.ok
        c.check_length([1, 2, 3]).should.be.ok

    def message(self):
        def cmd_name():
            pass
        c = MessageRH(cmd_name, BasicMessage)
        c.check_length(['a']).should_not.be.ok
        c.check_length(['a', 'b']).should.be.ok
        c.check_length(['a', 'b', 'c']).should.be.ok
        c.check_length(['a', 'b', 'c', 'd']).should.be.ok
        c.check_length(['a', 'b', 'c', 'd', 'e']).should_not.be.ok

    def json_message(self):
        def cmd_name():
            pass
        c = JsonMessageRH(cmd_name, JsonMessage)
        c.check_length(['a']).should_not.be.ok
        c.check_length(['a', 'b']).should.be.ok
        json_arg = dict(a=dict(b=2, c=[4, 5]), d=5, e=['a', 'z'])
        regular = [2, 3]
        args = c._extract_args(regular + json.dumps(json_arg).split())
        list(args).should.equal(regular + [json_arg])

__all__ = ('RequestHandlerSpec',)
