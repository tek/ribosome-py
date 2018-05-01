from typing import Any

from kallikrein import Expectation, k

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.io.api import N
from ribosome.nvim.api.variable import var_becomes
from ribosome.test.klk.matchers.nresult import nsuccess


def var_must_become(name: str, value: Any, timeout: float=3, interval: float=.2) -> NvimIO[Expectation]:
    return N.intercept(var_becomes(name, value, timeout, interval), lambda r: N.pure(k(r).must(nsuccess(True))))


__all__ = ('var_must_become',)
