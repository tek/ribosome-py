import json

from kallikrein import k, Expectation
from kallikrein.matchers import equal
from kallikrein.matchers.maybe import be_just

from amino.util.string import camelcase

from ribosome.request.legacy import RequestHandler1
from ribosome.machine.message_base import pmessage
from ribosome.request.handler import RequestDispatcher

BasicMessage = pmessage('BasicMessage', 'a', 'b', opt_fields=(('c', 1), ('d', 2)))
JsonMessage = pmessage('JsonMessage', 'a', 'b')


class RH(RequestHandler1):

    @property
    def desc(self):
        return 'req_test'

    @property
    def dispatcher(self) -> RequestDispatcher:
        ...


class RequestHandlerSpec:
    '''request handlers
    command name $name
    parameter count $nargs
    zero parameters $none
    one parameter $one
    one optional parameter $one_opt
    two parameters $two
    two parameters, one optional $two_one_opt
    two optional parameters $two_opt
    six parameters $six
    varargs $var
    '''

    def name(self) -> Expectation:
        def cmd_name(a, b, c=2):
            pass
        other_name = 'other_name'
        return (
            k(RH(cmd_name).vim_name).must(equal('CmdName')) &
            k(RH(cmd_name, name=other_name).vim_name).must(equal(camelcase(other_name)))
        )

    def nargs(self) -> Expectation:
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
            return (
                k(c.nargs).must(equal(nargs)) &
                k(c.count_spec).must(equal(spec))
            )
        return (
            check(none, '0', 'none') &
            check(one, '1', 'exactly 1') &
            check(two, '+', 'exactly 2') &
            check(two_default, '+', 'between 1 and 2') &
            check(more, '+', 'at least 3')
        )

    def none(self) -> Expectation:
        def fun():
            pass
        c = RH(fun)
        return (
            k(c.min).must(equal(0)) &
            k(c.max).must(be_just(0)) &
            k(c.check_length([])).true &
            k(c.check_length([1])).false
        )

    def one(self) -> Expectation:
        def fun(a):
            pass
        c = RH(fun)
        return (
            k(c.min).must(equal(1)) &
            k(c.max).must(be_just(1)) &
            k(c.check_length([])).false &
            k(c.check_length([1])).true &
            k(c.check_length([1, 2])).false
        )

    def one_opt(self) -> Expectation:
        def fun(a=1):
            pass
        c = RH(fun)
        return (
            k(c.min).must(equal(0)) &
            k(c.max).must(be_just(1)) &
            k(c.check_length([])).true &
            k(c.check_length([1])).true &
            k(c.check_length([1, 2])).false
        )

    def two(self) -> Expectation:
        def fun(a, b):
            pass
        c = RH(fun)
        return (
            k(c.min).must(equal(2)) &
            k(c.max).must(be_just(2)) &
            k(c.check_length([])).false &
            k(c.check_length([1])).false &
            k(c.check_length([1, 2])).true &
            k(c.check_length([1, 2, 3])).false
        )

    def two_one_opt(self) -> Expectation:
        def fun(a, b=1):
            pass
        c = RH(fun)
        return (
            k(c.min).must(equal(1)) &
            k(c.max).must(be_just(2)) &
            k(c.check_length([])).false &
            k(c.check_length([1])).true &
            k(c.check_length([1, 2])).true &
            k(c.check_length([1, 2, 3])).false
        )

    def two_opt(self) -> Expectation:
        def fun(a=1, b=1):
            pass
        c = RH(fun)
        return (
            k(c.min).must(equal(0)) &
            k(c.max).must(be_just(2)) &
            k(c.check_length([])).true &
            k(c.check_length([1])).true &
            k(c.check_length([1, 2])).true &
            k(c.check_length([1, 2, 3])).false
        )

    def six(self) -> Expectation:
        def fun(a, b, c, d, e, f):
            pass
        c = RH(fun)
        return (
            k(c.min).must(equal(6)) &
            k(c.max).must(be_just(6)) &
            k(c.check_length([])).false &
            k(c.check_length([1])).false &
            k(c.check_length([1, 2, 3, 4, 5, 6])).true &
            k(c.check_length([1, 2, 3, 4, 5, 6, 7])).false
        )

    def var(self) -> Expectation:
        def fun(a, b=1, *args):
            pass
        c = RH(fun)
        return (
            k(c.min).must(equal(1)) &
            k(c.max.is_just).false &
            k(c.check_length([])).false &
            k(c.check_length([1])).true &
            k(c.check_length([1, 2])).true &
            k(c.check_length([1, 2, 3])).true
        )

__all__ = ('RequestHandlerSpec',)
