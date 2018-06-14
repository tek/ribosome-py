from typing import Any, Callable

from kallikrein import Expectation, k
from kallikrein.matchers.either import be_right
from kallikrein.matchers.match_with import match_with

from amino import IO

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.variable import pvar_becomes


def run_test_io(io: Callable[..., IO[Expectation]], *a: Any, **kw: Any) -> Expectation:
    return k(io(*a, **kw).attempt).must(be_right(match_with(lambda a: a)))


def plugin_started() -> NvimIO[None]:
    return pvar_becomes('started', True, timeout=5)


__all__ = ('run_test_io', 'plugin_started',)
