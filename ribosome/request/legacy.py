import abc
import inspect
from numbers import Number
from typing import Callable, Any, Union

from amino import List, Maybe, Map
from amino.util.string import camelcase
from amino.boolean import true, false

from ribosome.logging import Logging
from ribosome.request.args import ParamsSpec, ArgValidator
from ribosome.request.handler.handler import RequestHandler
from ribosome.request.handler.dispatcher import RequestDispatcher, FunctionDispatcher
from ribosome.request.handler.prefix import Plain
from ribosome.request.handler.method import RpcMethod


def to_int(val: Union[int, str, None]) -> Union[int, str, None]:
    return int(val) if isinstance(val, str) and str.isdigit() else val


def numeric(val: Any) -> bool:
    return isinstance(val, Number)


class ParseError(Exception):
    pass


class LegacyRequestHandler(Logging, metaclass=abc.ABCMeta):

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

    def _call_fun(self, obj, *args, **kw):
        return self._fun(obj, *args)

    def dispatch(self, obj, rpc_args):
        argl = List.wrap(rpc_args)
        args = argl.head | List()
        bang = argl.lift(1).contains(1)
        validator = ArgValidator(self.params_spec)
        if validator.validate(args):
            return self._call_fun(obj, *args, bang=bang)
        else:
            return validator.error(args, self.desc, self.vim_name)

    @abc.abstractproperty
    def method(self) -> RpcMethod:
        ...

    @property
    def dispatcher(self) -> RequestDispatcher:
        return FunctionDispatcher(self._fun)

    @property
    def spec(self) -> RequestHandler:
        return RequestHandler(self.method, self.dispatcher, self.name, Plain(), false, true, self.kw)

__all__ = ('LegacyRequestHandler',)
