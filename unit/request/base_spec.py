from typing import Callable

from kallikrein import k, Expectation
from kallikrein.matchers import equal
from kallikrein.matchers.maybe import be_just

from amino.util.string import camelcase

from ribosome.request.legacy import LegacyRequestHandler
from ribosome.trans.message_base import pmessage
from ribosome.request.args import ArgValidator, ParamsSpec
from ribosome.request.nargs import NargsZero, NargsOne, NargsPlus
from ribosome.request.handler.dispatcher import RequestDispatcher

BasicMessage = pmessage('BasicMessage', 'a', 'b', opt_fields=(('c', 1), ('d', 2)))
JsonMessage = pmessage('JsonMessage', 'a', 'b')


class RH(LegacyRequestHandler):

    @property
    def desc(self):
        return 'req_test'

    @property
    def dispatcher(self) -> RequestDispatcher:
        ...


def check_args(fun: Callable, name: str=None) -> None:
    def check() -> None:
        return
    return check


class ArgValidatorSpec:
    '''request arg validation
    parameter count $nargs
    '''

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
            params = ParamsSpec.from_function(fun)
            v = ArgValidator(params)
            return (
                k(params.nargs).must(equal(nargs)) &
                k(v.count_spec).must(equal(spec))
            )
        return (
            check(none, NargsZero(), 'none') &
            check(one, NargsOne(), 'exactly 1') &
            check(two, NargsPlus(), 'exactly 2') &
            check(two_default, NargsPlus(), 'between 1 and 2') &
            check(more, NargsPlus(), 'at least 3')
        )


class RequestHandlerSpec:
    '''request handlers
    command name $name
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

    def none(self) -> Expectation:
        def fun():
            pass
        params = ParamsSpec.from_function(fun)
        v = ArgValidator(params)
        return (
            k(params.min).must(equal(0)) &
            k(params.max).must(be_just(0)) &
            k(v.validate([])).true &
            k(v.validate([1])).false
        )

    def one(self) -> Expectation:
        def fun(a):
            pass
        params = ParamsSpec.from_function(fun)
        v = ArgValidator(params)
        return (
            k(params.min).must(equal(1)) &
            k(params.max).must(be_just(1)) &
            k(v.validate([])).false &
            k(v.validate([1])).true &
            k(v.validate([1, 2])).false
        )

    def one_opt(self) -> Expectation:
        def fun(a=1):
            pass
        params = ParamsSpec.from_function(fun)
        v = ArgValidator(params)
        return (
            k(params.min).must(equal(0)) &
            k(params.max).must(be_just(1)) &
            k(v.validate([])).true &
            k(v.validate([1])).true &
            k(v.validate([1, 2])).false
        )

    def two(self) -> Expectation:
        def fun(a, b):
            pass
        params = ParamsSpec.from_function(fun)
        v = ArgValidator(params)
        return (
            k(params.min).must(equal(2)) &
            k(params.max).must(be_just(2)) &
            k(v.validate([])).false &
            k(v.validate([1])).false &
            k(v.validate([1, 2])).true &
            k(v.validate([1, 2, 3])).false
        )

    def two_one_opt(self) -> Expectation:
        def fun(a, b=1):
            pass
        params = ParamsSpec.from_function(fun)
        v = ArgValidator(params)
        return (
            k(params.min).must(equal(1)) &
            k(params.max).must(be_just(2)) &
            k(v.validate([])).false &
            k(v.validate([1])).true &
            k(v.validate([1, 2])).true &
            k(v.validate([1, 2, 3])).false
        )

    def two_opt(self) -> Expectation:
        def fun(a=1, b=1):
            pass
        params = ParamsSpec.from_function(fun)
        v = ArgValidator(params)
        return (
            k(params.min).must(equal(0)) &
            k(params.max).must(be_just(2)) &
            k(v.validate([])).true &
            k(v.validate([1])).true &
            k(v.validate([1, 2])).true &
            k(v.validate([1, 2, 3])).false
        )

    def six(self) -> Expectation:
        def fun(a, b, c, d, e, f):
            pass
        params = ParamsSpec.from_function(fun)
        v = ArgValidator(params)
        return (
            k(params.min).must(equal(6)) &
            k(params.max).must(be_just(6)) &
            k(v.validate([])).false &
            k(v.validate([1])).false &
            k(v.validate([1, 2, 3, 4, 5, 6])).true &
            k(v.validate([1, 2, 3, 4, 5, 6, 7])).false
        )

    def var(self) -> Expectation:
        def fun(a, b=1, *args):
            pass
        params = ParamsSpec.from_function(fun)
        v = ArgValidator(params)
        return (
            k(params.min).must(equal(1)) &
            k(params.max).must(~be_just) &
            k(v.validate([])).false &
            k(v.validate([1])).true &
            k(v.validate([1, 2])).true &
            k(v.validate([1, 2, 3])).true
        )

__all__ = ('RequestHandlerSpec',)
