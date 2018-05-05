from typing import Any, Callable

from kallikrein import Expectation, k
from kallikrein.matchers.either import be_right
from kallikrein.matchers.match_with import match_with

from amino import IO


def run_test_io(io: Callable[..., IO[Expectation]], *a: Any, **kw: Any) -> None:
    return k(io(*a, **kw).attempt).must(be_right(match_with(lambda a: a)))


__all__ = ('run_test_io',)
