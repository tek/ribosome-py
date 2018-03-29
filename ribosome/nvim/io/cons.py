from typing import TypeVar, Callable, Any

from amino import Either, Boolean
from amino.state import State

from ribosome.nvim.api.data import NvimApi
from ribosome.nvim.io.compute import NvimIOSuspend, NvimIOPure, NvimIOError, NvimIO, NvimIORecover
from ribosome.nvim.io.data import NError, NFatal

A = TypeVar('A')
B = TypeVar('B')


def nvimio_delay(f: Callable[..., A], *a: Any, **kw: Any) -> NvimIO[A]:
    return NvimIOSuspend.cons(State.inspect(lambda vim: NvimIOPure(f(vim, *a, **kw))))


def nvimio_suspend(f: Callable[..., NvimIO[A]], *a: Any, **kw: Any) -> NvimIO[A]:
    return NvimIOSuspend.cons(State.inspect(lambda vim: f(vim, *a, **kw)))


def nvimio_recover_error(fa: NvimIO[A], f: Callable[[str], NvimIO[A]]) -> NvimIO[A]:
    return NvimIORecover(fa, f, Boolean.is_a(NError))


def nvimio_recover_fatal(fa: NvimIO[A], f: Callable[[str], NvimIO[A]]) -> NvimIO[A]:
    return NvimIORecover(fa, f, Boolean.is_a(NFatal))


def nvimio_wrap_either(f: Callable[[NvimApi], Either[B, A]]) -> NvimIO[A]:
    return nvimio_suspend(lambda v: f(v).cata(NvimIOError, NvimIOPure))


def nvimio_from_either(e: Either[str, A]) -> NvimIO[A]:
    return e.cata(NvimIOError, NvimIOPure)


__all__ = ('nvimio_delay', 'nvimio_recover', 'nvimio_wrap_either', 'nvimio_from_either', 'nvimio_suspend',
           'nvimio_recover_fatal')
