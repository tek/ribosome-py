from traceback import FrameSummary
from typing import TypeVar, Callable, Any, Type

from msgpack import ExtType

from amino import Either, IO, Maybe, List
from amino.func import CallByName

from ribosome.nvim.api.data import NvimApi
from ribosome.nvim.io.compute import (NvimIOComputePure, NvimIOSuspend, NvimIORequest, NvimIOPure, NvimIOFatal,
                                      NvimIOError)
from ribosome.nvim.io import NvimIO
from ribosome.nvim.request import typechecked_request, data_cons_request, nvim_request

A = TypeVar('A')
B = TypeVar('B')


# TODO move all constructors here
class NMeta(type):

    @property
    def unit(self) -> NvimIO[A]:
        return N.pure(None)


class N(metaclass=NMeta):

    @staticmethod
    def wrap_either(f: Callable[[NvimApi], Either[B, A]], frame: FrameSummary=None) -> NvimIO[A]:
        return N.suspend(lambda v: f(v).cata(N.error, lambda a: (NvimIOComputePure(a, v), v)), _frame=frame)

    @staticmethod
    def from_either(e: Either[str, A], frame: FrameSummary=None) -> NvimIO[A]:
        return e.cata(N.error, N.pure)

    @staticmethod
    def e(e: Either[str, A], frame: FrameSummary=None) -> NvimIO[A]:
        return N.from_either(e, frame)

    @staticmethod
    def from_maybe(e: Maybe[A], error: CallByName, frame: FrameSummary=None) -> NvimIO[A]:
        return N.from_either(e.to_either(error), frame)

    @staticmethod
    def m(e: Maybe[A], error: CallByName, frame: FrameSummary=None) -> NvimIO[A]:
        return N.from_maybe(e, error, frame)

    @staticmethod
    def exception(exc: Exception) -> NvimIO[A]:
        return NvimIOFatal(exc)

    @staticmethod
    def failed(msg: str) -> NvimIO[A]:
        return N.exception(Exception(msg))

    @staticmethod
    def error(msg: str) -> NvimIO[A]:
        return NvimIOError(msg)

    @staticmethod
    def from_io(io: IO[A]) -> NvimIO[A]:
        return N.delay(lambda a: io.attempt.get_or_raise())

    @staticmethod
    def delay(f: Callable[..., A], *a: Any, **kw: Any) -> NvimIO[A]:
        def g(vim: NvimApi) -> A:
            return NvimIOComputePure(f(vim, *a, **kw), vim)
        return NvimIOSuspend(g)

    @staticmethod
    def request(method: str, args: List[str]) -> NvimIO[A]:
        return NvimIORequest(method, args)

    @staticmethod
    def simple(f: Callable[..., A], *a, **kw) -> NvimIO[A]:
        return N.delay(lambda v: f(*a, **kw))

    @staticmethod
    def suspend(f: Callable[..., NvimIO[A]], *a: Any, _frame: FrameSummary=None, **kw: Any) -> NvimIO[A]:
        def g(vim: NvimApi) -> NvimIO[A]:
            return f(vim, *a, **kw), vim
        return NvimIOSuspend(g, _frame)

    @staticmethod
    def pure(a: A) -> NvimIO[A]:
        return NvimIOPure(a)

    @staticmethod
    def read_tpe(cmd: str, tpe: Type[A], *args: Any) -> NvimIO[A]:
        return typechecked_request(cmd, tpe, *args)

    @staticmethod
    def read_cons(cmd: str, cons: Callable[[Any], Either[str, A]], *args: Any) -> NvimIO[A]:
        return data_cons_request(cmd, cons, *args)

    @staticmethod
    def read_ext(cmd: str, *args: Any) -> NvimIO[A]:
        return N.read_tpe(cmd, ExtType, *args)

    @staticmethod
    def write(cmd: str, *args: Any) -> NvimIO[A]:
        return nvim_request(cmd, *args).replace(None)

__all__ = ('N',)
