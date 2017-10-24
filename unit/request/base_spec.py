import json

from kallikrein import k, Expectation
from kallikrein.matchers import equal
from kallikrein.matchers.maybe import be_just

from ribosome.request.base import RequestHandler, MessageRequestHandler, JsonMessageRequestHandler
from ribosome.machine.message_base import pmessage

BasicMessage = pmessage('BasicMessage', 'a', 'b', opt_fields=(('c', 1), ('d', 2)))
JsonMessage = pmessage('JsonMessage', 'a', 'b')


class RH(RequestHandler):

    @property
    def desc(self):
        return 'req_test'


class MessageRH(RH, MessageRequestHandler):
    pass


class JsonMessageRH(RH, JsonMessageRequestHandler):
    pass


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
    message request handler $message
    json message request handler $json_pmessage
    '''

    def name(self) -> Expectation:
        def cmd_name(a, b, c=2):
            pass
        other_name = 'OtherName'
        return (
            k(RH(cmd_name).name).must(equal('CmdName')) &
            k(RH(cmd_name, other_name).name).must(equal(other_name))
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
            check(none, 0, 'none') &
            check(one, 1, 'exactly 1') &
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

    def message(self) -> Expectation:
        def cmd_name():
            pass
        c = MessageRH(cmd_name, BasicMessage)
        return (
            k(c.check_length(['a'])).false &
            k(c.check_length(['a', 'b'])).true &
            k(c.check_length(['a', 'b', 'c'])).true &
            k(c.check_length(['a', 'b', 'c', 'd'])).true &
            k(c.check_length(['a', 'b', 'c', 'd', 'e'])).false
        )

    def json_pmessage(self) -> Expectation:
        def cmd_name():
            pass
        c = JsonMessageRH(cmd_name, JsonMessage)
        json_arg = dict(a=dict(b=2, c=[4, 5]), d=5, e=['a', 'z'])
        regular = [2, 3]
        args = c._extract_args(regular + json.dumps(json_arg).split())
        return (
            k(c.check_length(['a'])).false &
            k(c.check_length(['a', 'b'])).true &
            k(list(args)).must(equal(regular + [json_arg]))
        )

__all__ = ('RequestHandlerSpec',)
