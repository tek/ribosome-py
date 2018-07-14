import time
from typing import TypeVar, Callable, Any, Type, Tuple

from msgpack import ExtType

from amino import Either, IO, Maybe, List, Boolean, do, Do
from amino.func import CallByName

from ribosome.nvim.api.data import NvimApi
from ribosome.nvim.io.compute import NvimIORequest, NvimIOPure, NvimIOFatal, NvimIOError, NvimIO
from ribosome.nvim.request import typechecked_request, data_cons_request, nvim_request
from ribosome.nvim.io.cons import (nvimio_delay, nvimio_recover_error, nvimio_recover_fatal, nvimio_wrap_either,
                                   nvimio_from_either, nvimio_suspend, nvimio_recover_failure, nvimio_ensure,
                                   nvimio_intercept)
from ribosome.nvim.io.data import NResult, NError, NFatal

A = TypeVar('A')
B = TypeVar('B')


class NMeta(type):

    @property
    def unit(self) -> NvimIO[None]:
        return N.pure(None)

    def pure(self, a: A) -> NvimIO[A]:
        return NvimIOPure(a)

    def wrap_either(self, f: Callable[[NvimApi], Either[B, A]]) -> NvimIO[A]:
        return nvimio_wrap_either(f)

    def from_either(self, e: Either[str, A]) -> NvimIO[A]:
        return nvimio_from_either(e)

    def e(self, e: Either[str, A]) -> NvimIO[A]:
        return N.from_either(e)

    def from_maybe(self, e: Maybe[A], error: CallByName) -> NvimIO[A]:
        return N.from_either(e.to_either(error))

    def m(self, e: Maybe[A], error: CallByName) -> NvimIO[A]:
        return N.from_maybe(e, error)

    def exception(self, exc: Exception) -> NvimIO[A]:
        return NvimIOFatal(exc)

    def failed(self, msg: str) -> NvimIO[A]:
        return N.exception(Exception(msg))

    def error(self, msg: str) -> NvimIO[A]:
        return NvimIOError(msg)

    def from_io(self, io: IO[A]) -> NvimIO[A]:
        return N.delay(lambda a: io.attempt.get_or_raise())

    def delay(self, f: Callable[..., A], *a: Any, **kw: Any) -> NvimIO[A]:
        return nvimio_delay(f, *a, **kw)

    def request(self, method: str, args: List[str], sync: bool=True) -> NvimIO[A]:
        return NvimIORequest(method, args, sync)

    def simple(self, f: Callable[..., A], *a: Any, **kw: Any) -> NvimIO[A]:
        return N.delay(lambda v: f(*a, **kw))

    def suspend(self, f: Callable[..., NvimIO[A]], *a: Any, **kw: Any) -> NvimIO[A]:
        return nvimio_suspend(f, *a, **kw)

    def read_tpe(self, cmd: str, tpe: Type[A], *args: Any) -> NvimIO[A]:
        return typechecked_request(cmd, tpe, *args)

    def read_cons(self, cmd: str, cons: Callable[[Any], Either[str, A]], *args: Any) -> NvimIO[A]:
        return data_cons_request(cmd, cons, *args)

    def read_ext(self, cmd: str, *args: Any) -> NvimIO[ExtType]:
        return N.read_tpe(cmd, ExtType, *args)

    def write(self, cmd: str, *args: Any, sync: bool=False) -> NvimIO[A]:
        return nvim_request(cmd, *args, sync=sync).replace(None)

    def intercept(self, fa: NvimIO[A], f: Callable[[NResult[A]], NvimIO[B]]) -> NvimIO[B]:
        return nvimio_intercept(fa, f)

    def safe(self, fa: NvimIO[A]) -> NvimIO[NResult[A]]:
        return N.intercept(fa, N.pure)

    def recover_error(self, fa: NvimIO[A], f: Callable[[NResult[A]], NvimIO[A]]) -> NvimIO[A]:
        return nvimio_recover_error(fa, f)

    def recover_fatal(self, fa: NvimIO[A], f: Callable[[NResult[A]], NvimIO[A]]) -> NvimIO[A]:
        return nvimio_recover_fatal(fa, f)

    def recover_failure(self, fa: NvimIO[A], f: Callable[[NResult[A]], NvimIO[A]]) -> NvimIO[A]:
        return nvimio_recover_failure(fa, f)

    def ignore_failure(self, fa: NvimIO[A]) -> NvimIO[None]:
        return nvimio_recover_failure(fa, lambda a: N.unit)

    def ensure(self, fa: NvimIO[A], f: Callable[[NResult[A]], NvimIO[None]]) -> NvimIO[A]:
        return nvimio_ensure(fa, f, lambda a: True)

    def ensure_error(self, fa: NvimIO[A], f: Callable[[NResult[A]], NvimIO[None]]) -> NvimIO[A]:
        return nvimio_ensure(fa, f, Boolean.is_a(NError))

    def ensure_fatal(self, fa: NvimIO[A], f: Callable[[NResult[A]], NvimIO[None]]) -> NvimIO[A]:
        return nvimio_ensure(fa, f, Boolean.is_a(NFatal))

    def ensure_failure(self, fa: NvimIO[A], f: Callable[[NResult[A]], NvimIO[None]]) -> NvimIO[A]:
        return nvimio_ensure(fa, f, Boolean.is_a((NError, NFatal)))

    @do(IO[Tuple[NvimApi, A]])
    def to_io(self, fa: NvimIO[A], api: NvimApi) -> Do:
        api1, result = yield IO.delay(fa.run, api)
        result_strict = yield IO.from_either(result.to_either)
        return api1, result_strict

    @do(IO[NvimApi])
    def to_io_s(self, fa: NvimIO[A], api: NvimApi) -> Do:
        api1, result = yield N.to_io(fa, api)
        return api1

    @do(IO[A])
    def to_io_a(self, fa: NvimIO[A], api: NvimApi) -> Do:
        api1, result = yield N.to_io(fa, api)
        return result

    def sleep(self, duration: float) -> NvimIO[None]:
        return N.delay(lambda v: time.sleep(duration))


class N(metaclass=NMeta):
    pass

__all__ = ('N',)
