from typing import Callable

from kallikrein import k, Expectation
from kallikrein.matchers import equal
from kallikrein.matchers.maybe import be_just

from ribosome.rpc.args import ParamsSpec, ArgValidator
from ribosome.rpc.data.nargs import NargsZero, NargsOne, NargsPlus


def check_args(fun: Callable, name: str=None) -> None:
    def check() -> None:
        return
    return check


class ArgValidatorSpec:
    '''request arg validation
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


    def none(self) -> Expectation:
        def fun():
            pass
        params = ParamsSpec.from_function(fun)
        v = ArgValidator(params)
        return (
            k(params.min).must(equal(0)) &
            k(params.max).must(be_just(0)) &
            k(v.validate(0)).true &
            k(v.validate(1)).false
        )

    def one(self) -> Expectation:
        def fun(a):
            pass
        params = ParamsSpec.from_function(fun)
        v = ArgValidator(params)
        return (
            k(params.min).must(equal(1)) &
            k(params.max).must(be_just(1)) &
            k(v.validate(0)).false &
            k(v.validate(1)).true &
            k(v.validate(2)).false
        )

    def one_opt(self) -> Expectation:
        def fun(a=1):
            pass
        params = ParamsSpec.from_function(fun)
        v = ArgValidator(params)
        return (
            k(params.min).must(equal(0)) &
            k(params.max).must(be_just(1)) &
            k(v.validate(0)).true &
            k(v.validate(1)).true &
            k(v.validate(2)).false
        )

    def two(self) -> Expectation:
        def fun(a, b):
            pass
        params = ParamsSpec.from_function(fun)
        v = ArgValidator(params)
        return (
            k(params.min).must(equal(2)) &
            k(params.max).must(be_just(2)) &
            k(v.validate(0)).false &
            k(v.validate(1)).false &
            k(v.validate(2)).true &
            k(v.validate(3)).false
        )

    def two_one_opt(self) -> Expectation:
        def fun(a, b=1):
            pass
        params = ParamsSpec.from_function(fun)
        v = ArgValidator(params)
        return (
            k(params.min).must(equal(1)) &
            k(params.max).must(be_just(2)) &
            k(v.validate(0)).false &
            k(v.validate(1)).true &
            k(v.validate(2)).true &
            k(v.validate(3)).false
        )

    def two_opt(self) -> Expectation:
        def fun(a=1, b=1):
            pass
        params = ParamsSpec.from_function(fun)
        v = ArgValidator(params)
        return (
            k(params.min).must(equal(0)) &
            k(params.max).must(be_just(2)) &
            k(v.validate(0)).true &
            k(v.validate(1)).true &
            k(v.validate(2)).true &
            k(v.validate(3)).false
        )

    def six(self) -> Expectation:
        def fun(a, b, c, d, e, f):
            pass
        params = ParamsSpec.from_function(fun)
        v = ArgValidator(params)
        return (
            k(params.min).must(equal(6)) &
            k(params.max).must(be_just(6)) &
            k(v.validate(0)).false &
            k(v.validate(1)).false &
            k(v.validate(6)).true &
            k(v.validate(7)).false
        )

    def var(self) -> Expectation:
        def fun(a, b=1, *args):
            pass
        params = ParamsSpec.from_function(fun)
        v = ArgValidator(params)
        return (
            k(params.min).must(equal(1)) &
            k(params.max).must(~be_just) &
            k(v.validate(0)).false &
            k(v.validate(1)).true &
            k(v.validate(2)).true &
            k(v.validate(3)).true
        )


__all__ = ('ArgValidatorSpec',)
