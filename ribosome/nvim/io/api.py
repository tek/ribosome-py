from typing import TypeVar, Callable, Any, Type

from msgpack import ExtType

from amino import Either, IO, Maybe, List, do, Do
from amino.func import CallByName

from ribosome.nvim.api.data import NvimApi
from ribosome.nvim.io.compute import NvimIORequest, NvimIOPure, NvimIOFatal, NvimIOError, NvimIO
from ribosome.nvim.request import typechecked_request, data_cons_request, nvim_request
from ribosome.nvim.io.cons import (nvimio_delay, nvimio_recover_error, nvimio_recover_fatal, nvimio_wrap_either,
                                   nvimio_from_either, nvimio_suspend)

A = TypeVar('A')
B = TypeVar('B')


class NMeta(type):

    @property
    def unit(self) -> NvimIO[A]:
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

    def request(self, method: str, args: List[str]) -> NvimIO[A]:
        return NvimIORequest(method, args)

    def simple(self, f: Callable[..., A], *a, **kw) -> NvimIO[A]:
        return N.delay(lambda v: f(*a, **kw))

    def suspend(self, f: Callable[..., NvimIO[A]], *a: Any, **kw: Any) -> NvimIO[A]:
        return nvimio_suspend(f, *a, **kw)

    def read_tpe(self, cmd: str, tpe: Type[A], *args: Any) -> NvimIO[A]:
        return typechecked_request(cmd, tpe, *args)

    def read_cons(self, cmd: str, cons: Callable[[Any], Either[str, A]], *args: Any) -> NvimIO[A]:
        return data_cons_request(cmd, cons, *args)

    def read_ext(self, cmd: str, *args: Any) -> NvimIO[A]:
        return N.read_tpe(cmd, ExtType, *args)

    def write(self, cmd: str, *args: Any) -> NvimIO[A]:
        return nvim_request(cmd, *args).replace(None)

    def recover_error(self, fa: NvimIO[A], f: Callable[[str], B]) -> NvimIO[B]:
        return nvimio_recover_error(fa, f)

    def recover_fatal(self, fa: NvimIO[A], f: Callable[[Exception], NvimIO[B]]) -> NvimIO[B]:
        return nvimio_recover_fatal(fa, f)

    @do(NvimIO[A])
    def ensure(self, fa: NvimIO[A], f: Callable[[Either[Exception, A]], NvimIO[None]]) -> Do:
        result = yield N.delay(fa.either)
        yield f(result)
        yield N.from_either(result)

    def effect(self, fa: NvimIO[A], f: Callable[[A], Any]) -> NvimIO[A]:
        def wrap(vim: NvimApi) -> A:
            ret = fa.run(vim)
            f(ret)
            return ret
        return N.delay(wrap)

    __mod__ = effect

    def error_effect(self, fa: NvimIO[A], f: Callable[[Exception], None]) -> 'NvimIO[A]':
        return fa.ensure(lambda a: N.delay(lambda vim: a.leffect(f)))

    def error_effect_f(self, fa: NvimIO[A], f: Callable[[Exception], 'NvimIO[None]']) -> 'NvimIO[A]':
        return N.ensure(fa, lambda a: N.suspend(lambda vim: a.cata(f, N.pure)))


class N(metaclass=NMeta):
    pass

__all__ = ('N',)
