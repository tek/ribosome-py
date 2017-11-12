import abc
import json
import inspect
from numbers import Number
from typing import Callable, Any, Tuple, Union, Generic, TypeVar, Type

from amino import List, Maybe, may, _, Just, Map, Try, Boolean, Lists, Nothing
from amino.util.string import camelcase
from amino.dat import Dat
from amino.algebra import Algebra
from amino.boolean import false

import ribosome
from ribosome.machine.message_base import Message
from ribosome.logging import Logging
from ribosome.request.handler import RequestHandler, RequestDispatcher, Plain


def to_int(val: Union[int, str, None]) -> Union[int, str, None]:
    return int(val) if isinstance(val, str) and str.isdigit() else val


def numeric(val: Any) -> bool:
    return isinstance(val, Number)


class ParseError(Exception):
    pass


class Nargs(Algebra):

    @staticmethod
    def cons(min: int, mmax: Maybe[int]) -> 'Nargs':
        def from_min() -> Nargs:
            return NargsStar() if min == 0 else NargsPlus()
        def with_max(max: int) -> Nargs:
            return (
                Just(NargsZero())
                if max == 0 else
                (
                    Just(NargsOne())
                    if min == 1 else
                    Just(NargsQM())
                )
                if max == 1 else
                Nothing
            )
        return mmax.flat_map(with_max) | from_min

    @abc.abstractproperty
    def for_vim(self) -> str:
        ...

    def _arg_desc(self) -> List[str]:
        return List()


class NargsZero(Nargs):

    @property
    def for_vim(self) -> str:
        return '0'


class NargsOne(Nargs):

    @property
    def for_vim(self) -> str:
        return '1'


class NargsStar(Nargs):

    @property
    def for_vim(self) -> str:
        return '*'


class NargsPlus(Nargs):

    @property
    def for_vim(self) -> str:
        return '+'


class NargsQM(Nargs):

    @property
    def for_vim(self) -> str:
        return '?'


class ParamsSpec(Dat['ParamsSpec']):

    @staticmethod
    def from_function(fun: Callable[..., Any]) -> 'ParamsSpec':
        argspec = inspect.getfullargspec(fun)
        params = Lists.wrap(argspec.args)
        defaults = Lists.wrap(argspec.defaults or ())
        method = Boolean(params.head.contains('self'))
        param_count = params.length - method.to_int
        min = param_count - defaults.length
        max = (~Boolean(argspec.varargs or argspec.varkw)).m(param_count)
        nargs = Nargs.cons(min, max)
        return ParamsSpec(nargs, min, max, method)

    def __init__(self, nargs: Nargs, min: int, max: Maybe[int], method: Boolean) -> None:
        self.nargs = nargs
        self.min = min
        self.max = max
        self.method = method


class ArgValidator:

    def __init__(self, spec: ParamsSpec) -> None:
        self.spec = spec

    def validate(self, args: tuple) -> Boolean:
        return false


class RequestHandler1(Logging, metaclass=abc.ABCMeta):

    def __init__(
            self,
            fun: Callable[..., Any],
            name: str=None,
            nargs: Union[str, int]=None,
            min: int=None,
            max: int=None,
            **kw: str
    ) -> None:
        self._fun = fun
        self._argspec = inspect.getfullargspec(fun)
        self._params = List.wrap(self._argspec.args)
        self._param_count = self._params.length - (1 if self._params.head.contains('self') else 0)
        self._name = Maybe(name)
        self._nargs = Maybe(to_int(nargs))
        self._min = Maybe(min)
        self._max = Maybe(max)
        self._kw = Map(kw)
        self.params_spec = ParamsSpec.from_function(self._fun)

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
    def nargs(self) -> Union[str, int]:
        return self._nargs\
            .map(lambda a: '+' if numeric(a) and a > 1 else a)\
            .get_or_else(self.params_spec.nargs.for_vim)

    @property
    def min(self):
        return self._min.get_or_else(self.params_spec.min)

    @property
    def max(self):
        return self._max.or_else(self.params_spec.max)

    @property
    def vim_name(self) -> str:
        return camelcase(self.name)

    @property
    def name(self) -> str:
        return self._name.get_or_else(self._infer_name)

    @property
    def _infer_name(self):
        return self._fun.__name__

    @property
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
        err = msg.format(self.desc, self.vim_name, len(args), self.count_spec, args)
        self.log.error(err)
        return err

    def _call_fun(self, obj, *args, **kw):
        return self._fun(obj, *args)

    def dispatch(self, obj, rpc_args):
        argl = List.wrap(rpc_args)
        args = argl.head | List()
        bang = argl.lift(1).contains(1)
        # validator = ArgValidator(self.params_spec)
        if self.check_length(args):
            return self._call_fun(obj, *args, bang=bang)
        else:
            return self.error(args)

    @abc.abstractproperty
    def dispatcher(self) -> RequestDispatcher:
        ...

    @property
    def spec(self) -> RequestHandler:
        return RequestHandler(self.dispatcher, self.name, Plain(), self.kw.lift('sync').true, self.kw)

__all__ = ('RequestHandler1',)
