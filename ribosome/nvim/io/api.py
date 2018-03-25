from traceback import FrameSummary
from typing import TypeVar, Callable, Any, Type

from msgpack import ExtType

from amino import Either, IO, Maybe, List, do, Do
from amino.func import CallByName
from amino.state import EitherState

from ribosome.nvim.api.data import NvimApi
from ribosome.nvim.io.compute import NvimIOSuspend, NvimIORequest, NvimIOPure, NvimIOFatal, NvimIOError
from ribosome.nvim.io import NvimIO
from ribosome.nvim.request import typechecked_request, data_cons_request, nvim_request

A = TypeVar('A')
B = TypeVar('B')


# TODO move all constructors here
class NMeta(type):

    @property
    def unit(self) -> NvimIO[A]:
        return N.pure(None)

    def pure(self, a: A) -> NvimIO[A]:
        return NvimIOPure(a)

    def wrap_either(self, f: Callable[[NvimApi], Either[B, A]], frame: FrameSummary=None) -> NvimIO[A]:
        return N.suspend(lambda v: f(v).cata(N.error, lambda a: (NvimIOPure(a), v)), _frame=frame)

    def from_either(self, e: Either[str, A], frame: FrameSummary=None) -> NvimIO[A]:
        return e.cata(N.error, N.pure)

    def e(self, e: Either[str, A], frame: FrameSummary=None) -> NvimIO[A]:
        return N.from_either(e, frame)

    def from_maybe(self, e: Maybe[A], error: CallByName, frame: FrameSummary=None) -> NvimIO[A]:
        return N.from_either(e.to_either(error), frame)

    def m(self, e: Maybe[A], error: CallByName, frame: FrameSummary=None) -> NvimIO[A]:
        return N.from_maybe(e, error, frame)

    def exception(self, exc: Exception) -> NvimIO[A]:
        return NvimIOFatal(exc)

    def failed(self, msg: str) -> NvimIO[A]:
        return N.exception(Exception(msg))

    def error(self, msg: str) -> NvimIO[A]:
        return NvimIOError(msg)

    def from_io(self, io: IO[A]) -> NvimIO[A]:
        return N.delay(lambda a: io.attempt.get_or_raise())

    def delay(self, f: Callable[..., A], *a: Any, **kw: Any) -> NvimIO[A]:
        def thunk(self, vim: NvimApi) -> A:
            return vim, NvimIOPure(f(vim, *a, **kw))
        return NvimIOSuspend.cons(EitherState.inspect(lambda vim: NvimIOPure(f(vim, *a, **kw))))

    def request(self, method: str, args: List[str]) -> NvimIO[A]:
        return NvimIORequest(method, args)

    def simple(self, f: Callable[..., A], *a, **kw) -> NvimIO[A]:
        return N.delay(lambda v: f(*a, **kw))

    def suspend(self, f: Callable[..., NvimIO[A]], *a: Any, **kw: Any) -> NvimIO[A]:
        return NvimIOSuspend.cons(EitherState.inspect(lambda vim: f(vim, *a, **kw)))

    def read_tpe(self, cmd: str, tpe: Type[A], *args: Any) -> NvimIO[A]:
        return typechecked_request(cmd, tpe, *args)

    def read_cons(self, cmd: str, cons: Callable[[Any], Either[str, A]], *args: Any) -> NvimIO[A]:
        return data_cons_request(cmd, cons, *args)

    def read_ext(self, cmd: str, *args: Any) -> NvimIO[A]:
        return N.read_tpe(cmd, ExtType, *args)

    def write(self, cmd: str, *args: Any) -> NvimIO[A]:
        return nvim_request(cmd, *args).replace(None)

    def recover(self, fa: NvimIO[A], f: Callable[[Exception], B]) -> NvimIO[B]:
        return NvimIO.delay(fa.either).map(lambda a: a.value_or(f))

    def recover_with(self, fa: NvimIO[A], f: Callable[[Exception], NvimIO[B]]) -> NvimIO[B]:
        return NvimIO.delay(fa.either).flat_map(lambda a: a.map(NvimIO.pure).value_or(f))

    @do(NvimIO[A])
    def ensure(self, fa: NvimIO[A], f: Callable[[Either[Exception, A]], NvimIO[None]]) -> Do:
        result = yield NvimIO.delay(fa.either)
        yield f(result)
        yield NvimIO.from_either(result)

    def effect(self, fa: NvimIO[A], f: Callable[[A], Any]) -> NvimIO[A]:
        def wrap(vim: NvimApi) -> A:
            ret = fa.run(vim)
            f(ret)
            return ret
        return NvimIO.delay(wrap)

    __mod__ = effect

    def error_effect(self, fa: NvimIO[A], f: Callable[[Exception], None]) -> 'NvimIO[A]':
        return fa.ensure(lambda a: NvimIO.delay(lambda vim: a.leffect(f)))

    def error_effect_f(self, fa: NvimIO[A], f: Callable[[Exception], 'NvimIO[None]']) -> 'NvimIO[A]':
        return fa.ensure(lambda a: NvimIO.suspend(lambda vim: a.cata(f, NvimIO.pure)))


class N(metaclass=NMeta):
    pass

__all__ = ('N',)
