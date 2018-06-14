from typing import Callable, Any, TypeVar

from kallikrein.expectation import LiftExpectationResult, ExpectationResult, FatalSpecResult
from kallikrein import Expectation, k
from kallikrein.matcher import Matcher

from amino import do, Do

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.util import nvimio_repeat_timeout
from ribosome.nvim.io.api import N
from ribosome.nvim.io.data import NError, NResult

A = TypeVar('A')


def failure_result(expectation: Callable[..., NvimIO[Expectation]], *a: Any, **kw: Any) -> NvimIO[ExpectationResult]:
    def failure_result(result: NError[Expectation]) -> NvimIO[ExpectationResult]:
        return expectation(*a, **kw)
    return failure_result


@do(NvimIO[ExpectationResult])
def eval_expectation(expectation: Callable[..., NvimIO[Expectation]], *a: Any, **kw: Any) -> Do:
    exp = yield expectation(*a, **kw)
    yield N.from_io(exp.evaluate)


def failed_expectation(result: NResult[A]) -> NvimIO[ExpectationResult]:
    return N.pure(FatalSpecResult('await_k', Exception(str(result))))


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
            lambda: N.recover_failure(eval_expectation(expectation, *a, **kw), failed_expectation),
            lambda a: a.success,
            f'expectation not satisfied within {timeout} seconds',
            timeout,
            interval,
        ).map(LiftExpectationResult),
        failure_result(expectation, *a, **kw),
    )


@do(NvimIO[Expectation])
def await_k_with(
        matcher: Matcher[A],
        thunk: Callable[..., NvimIO[A]],
        *a: Any,
        timeout: int=1,
        interval: float=.25,
        **kw: Any,
) -> Do:
    yield await_k(lambda: thunk(*a, **kw).map(lambda a: k(a).must(matcher)), timeout=timeout, interval=interval)


__all__ = ('await_k', 'await_k_with',)
