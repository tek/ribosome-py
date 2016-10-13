import abc
import json
import inspect
from typing import Callable, Any, Tuple

from amino import List, Maybe, Right, Left, may, _, Just, Map, Try
from amino.util.string import camelcaseify

import ribosome
from ribosome.logging import Logging


def parse_int(i):
    return Right(i) if isinstance(i, int) else (
        Right(int(i)) if isinstance(i, str) and i.isdigit() else
        Left('could not parse int {}'.format(i))
    )


def try_int(val):
    return int(val) if isinstance(val, str) and str.isdigit() else val


def numeric(val):
    return isinstance(val, int)


class ParseError(Exception):
    pass


class RequestHandler(Logging, metaclass=abc.ABCMeta):

    def __init__(
            self,
            fun: Callable[..., Any],
            name: str=None,
            nargs=None,
            min: int=None,
            max: int=None,
            **kw
    ) -> None:
        self._fun = fun
        self._argspec = inspect.getfullargspec(fun)  # type: ignore
        self._params = List.wrap(self._argspec.args)
        self._param_count = self._params.length - (
            1 if self._params.head.contains('self') else 0
        )
        self._name = Maybe(name)
        self._nargs = Maybe(try_int(nargs))
        self._min = Maybe(min)
        self._max = Maybe(max)
        self._kw = kw

    @abc.abstractproperty
    def desc(self):
        ...

    @property
    def kw(self):
        return self.default_kw ** self._kw

    @property
    def default_kw(self):
        return Map()

    @property
    def nargs(self):
        return self._nargs\
            .map(lambda a: '+' if numeric(a) and a > 1 else a)\
            .get_or_else(self._infer_nargs)

    @property
    def _infer_nargs(self):
        if self.min > 1:
            return '+'
        elif self.min == 1:
            return 1 if self.max.contains(1) else '+'
        else:
            if self.max.contains(0):
                return 0
            if self.max.contains(1):
                return '?'
            else:
                return '*'

    @property
    def min(self):
        return self._min.get_or_else(self._infer_min)

    @property
    def _infer_min(self):
        s = self._argspec
        return self._param_count - len(s.defaults or [])

    @property
    def max(self):
        return self._max.or_else(self._infer_max)

    @property  # type: ignore
    @may
    def _infer_max(self):
        s = self._argspec
        if not (s.varargs or s.varkw):
            return self._param_count

    @property
    def name(self):
        return self._name.get_or_else(self._infer_name)

    @property
    def _infer_name(self):
        return camelcaseify(self._fun.__name__)

    @property  # type: ignore
    @may
    def exact_count(self):
        if self.max.contains(self.min):
            return self.min

    def check_length(self, args):
        l = len(args)
        return (
            self.min <= l and
            not self.max.exists(_ < l)
        )

    @property
    def count_spec(self):
        return self.exact_count\
            .map(lambda a: 'exactly {}'.format(a) if a else 'none')\
            .get_or_else(
                (Just(self.min) & self.max)
                .map2('between {} and {}'.format) |
                'at least {}'.format(self.min)
            )

    def error(self, args):
        msg = 'argument count for {} "{}" is {}, must be {} ({})'
        err = msg.format(self.desc, self.name, len(args), self.count_spec,
                         args)
        self.log.error(err)
        return err

    def _call_fun(self, obj, *args):
        return self._fun(obj, *args)

    def dispatch(self, obj, rpc_args):
        args = List.wrap(rpc_args).lift(0).get_or_else(List())
        if self.check_length(args):
            return self._call_fun(obj, *args)
        else:
            return self.error(args)


class MessageRequestHandler(RequestHandler):

    def __init__(self, fun: Callable[[], Any], msg: type, **kw) -> None:
        self._message = msg
        self._fun_name = fun.__name__
        super().__init__(self._message.__init__, **kw)  # type: ignore

    @property
    def _infer_name(self):
        return camelcaseify(self._fun_name)

    @property
    def min(self):
        return self._message._field_count_min

    @property
    def max(self):
        return self._message._field_count_max

    def _call_fun(self, obj, *args):
        if isinstance(obj, ribosome.NvimStatePlugin):
            obj.state.send(self._message(*args))
        else:
            msg = 'msg_{} can only be used on NvimStatePlugin ({})'
            self.log.error(msg.format(self.desc, obj))

    @property
    def msg_dispatch(self):
        def msg_dispatch_wrapper(obj, *rpc_args):
            return self.dispatch(obj, rpc_args)
        return msg_dispatch_wrapper


class JsonMessageRequestHandler(MessageRequestHandler):

    def __init__(self, fun: Callable[[], Any], msg: type, **kw) -> None:
        super(JsonMessageRequestHandler, self).__init__(fun, msg, **kw)

    @property
    def nargs(self):
        return '+' if self.min > 0 else '*'

    @property  # type: ignore
    @may
    def max(self):
        pass

    def _extract_args(self, args: Tuple[str]):
        def parse(d):
            def fail(err):
                raise ParseError('neither valid json nor python: {}'.format(d))
            return (
                Try(json.loads, d)
                .o(lambda: Try(eval, d))
                .o(lambda: Try(json.loads, d.replace('\\"', '"')))
                .right_or_map(fail)
            )
        pos_args, data_args = (tuple(args[:self.min]),  # type: ignore
                               tuple(args[self.min:]))  # type: ignore
        data = ' '.join(data_args)
        params = parse(data) if data else {}
        return pos_args + (Map(params),)

    def _call_fun(self, obj, *args):
        try:
            real_args = self._extract_args(args)
        except ParseError as e:
            self.log.error(e)
        else:
            super(JsonMessageRequestHandler, self)._call_fun(obj, *real_args)

__all__ = ('RequestHandler', 'MessageRequestHandler',
           'JsonMessageRequestHandler')
