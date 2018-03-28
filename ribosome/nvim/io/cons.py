from typing import TypeVar, Callable, Any

from amino import Either
from amino.state import State

from ribosome.nvim.api.data import NvimApi
from ribosome.nvim.io.compute import NvimIOSuspend, NvimIOPure, NvimIOError, NvimIO

A = TypeVar('A')
B = TypeVar('B')


def nvimio_delay(f: Callable[..., A], *a: Any, **kw: Any) -> NvimIO[A]:
    return NvimIOSuspend.cons(State.inspect(lambda vim: NvimIOPure(f(vim, *a, **kw))))


def nvimio_suspend(f: Callable[..., NvimIO[A]], *a: Any, **kw: Any) -> NvimIO[A]:
    return NvimIOSuspend.cons(State.inspect(lambda vim: f(vim, *a, **kw)))


def nvimio_recover(fa: NvimIO[A], f: Callable[[Exception], B]) -> NvimIO[B]:
    return nvimio_delay(fa.either).map(lambda a: a.value_or(f))


def nvimio_recover_with(fa: NvimIO[A], f: Callable[[Exception], NvimIO[B]]) -> NvimIO[B]:
    return nvimio_delay(fa.either).flat_map(lambda a: a.cata(f, NvimIOPure))


def nvimio_wrap_either(f: Callable[[NvimApi], Either[B, A]]) -> NvimIO[A]:
    return nvimio_suspend(lambda v: f(v).cata(NvimIOError, NvimIOPure))


def nvimio_from_either(e: Either[str, A]) -> NvimIO[A]:
    return e.cata(NvimIOError, NvimIOPure)


__all__ = ('nvimio_delay', 'nvimio_recover', 'nvimio_recover_with', 'nvimio_wrap_either', 'nvimio_from_either',
           'nvimio_suspend')
