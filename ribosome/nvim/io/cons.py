from typing import TypeVar, Callable, Any

from amino import Either, Boolean, do, Do
from amino.state import State
from amino.boolean import true

from ribosome.nvim.api.data import NvimApi
from ribosome.nvim.io.compute import NvimIOSuspend, NvimIOPure, NvimIOError, NvimIO, NvimIORecover, lift_n_result
from ribosome.nvim.io.data import NError, NFatal, NResult

A = TypeVar('A')
B = TypeVar('B')


def nvimio_suspend(f: Callable[..., NvimIO[A]], *a: Any, **kw: Any) -> NvimIO[A]:
    return NvimIOSuspend.cons(State.inspect(lambda vim: f(vim, *a, **kw)))


def nvimio_delay(f: Callable[..., A], *a: Any, **kw: Any) -> NvimIO[A]:
    return nvimio_suspend(lambda vim: NvimIOPure(f(vim, *a, **kw)))


def nvimio_recover_error(fa: NvimIO[A], f: Callable[[NResult[A]], NvimIO[A]]) -> NvimIO[A]:
    return NvimIORecover(fa, f, Boolean.is_a(NError))


def nvimio_intercept(fa: NvimIO[A], f: Callable[[NResult[A]], NvimIO[B]]) -> NvimIO[B]:
    return NvimIORecover(fa, f, lambda r: true)


def nvimio_recover_fatal(fa: NvimIO[A], f: Callable[[NResult[A]], NvimIO[A]]) -> NvimIO[A]:
    return NvimIORecover(fa, f, Boolean.is_a(NFatal))


def nvimio_recover_failure(fa: NvimIO[A], f: Callable[[NResult[A]], NvimIO[A]]) -> NvimIO[A]:
    return NvimIORecover(fa, f, Boolean.is_a((NError, NFatal)))


def nvimio_ensure(fa: NvimIO[A], f: Callable[[NResult[A]], NvimIO[None]], pred: Callable[[NResult[A]], bool]
                  ) -> NvimIO[A]:
    @do(NvimIO[A])
    def effect(error: NResult[A]) -> Do:
        yield f(error)
        yield lift_n_result.match(error)
    return NvimIORecover(fa, effect, pred)


def nvimio_wrap_either(f: Callable[[NvimApi], Either[B, A]]) -> NvimIO[A]:
    return nvimio_suspend(lambda v: f(v).cata(NvimIOError, NvimIOPure))


def nvimio_from_either(e: Either[str, A]) -> NvimIO[A]:
    return e.cata(NvimIOError, NvimIOPure)


__all__ = ('nvimio_delay', 'nvimio_wrap_either', 'nvimio_from_either', 'nvimio_suspend', 'nvimio_recover_error',
           'nvimio_recover_fatal', 'nvimio_recover_failure', 'nvimio_ensure', 'nvimio_intercept')
