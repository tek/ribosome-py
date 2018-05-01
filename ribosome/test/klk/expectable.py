from typing import TypeVar, Callable, Any

from kallikrein import kf
from kallikrein.expectable import Expectable

from ribosome.nvim.api.data import NvimApi
from ribosome.nvim.io.compute import NvimIO

A = TypeVar('A')


def kn(vim: NvimApi, f: Callable[..., NvimIO[A]], *a: Any, **kw: Any) -> Expectable:
    return kf(lambda: f(*a, **kw).result(vim))


def kns(vim: NvimApi, f: Callable[..., NvimIO[A]], *a: Any, **kw: Any) -> Expectable:
    return kf(lambda: f(*a, **kw).run_s(vim))


__all__ = ('kn', 'kns')
