from typing import Callable, Any

from kallikrein.expectation import LiftExpectationResult, ExpectationResult
from kallikrein import Expectation

from amino import do, Do

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.util import nvimio_repeat_timeout
from ribosome.nvim.io.api import N
from ribosome.nvim.io.data import NError


def failure_result(expectation: Callable[..., NvimIO[Expectation]], *a: Any, **kw: Any) -> NvimIO[ExpectationResult]:
    def failure_result(result: NError[Expectation]) -> NvimIO[ExpectationResult]:
        return expectation(*a, **kw)
    return failure_result


@do(NvimIO[Expectation])
def eval_expectation(expectation: Callable[..., NvimIO[Expectation]], *a: Any, **kw: Any) -> Do:
    io = yield expectation(*a, **kw)
    yield N.from_io(io.evaluate)


@do(NvimIO[Expectation])
def await_k(
        expectation: Callable[..., NvimIO[Expectation]],
        *a: Any,
        timeout: int=1,
        interval: float=.25,
        **kw: Any,
) -> Do:
    yield N.recover_error(
        nvimio_repeat_timeout(
            lambda: eval_expectation(expectation, *a, **kw),
            lambda a: a.success,
            f'expectation not satisfied within {timeout} seconds',
            timeout,
            interval,
        ).map(LiftExpectationResult),
        failure_result(expectation, *a, **kw),
    )


__all__ = ('await_k',)
