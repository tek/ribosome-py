from typing import TypeVar, Callable, Any

from ribosome.nvim.api.data import NvimApi
from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.io.data import NResult, NSuccess

from kallikrein import kf
from kallikrein.expectable import Expectable
from kallikrein.matchers.contain import PredContain, NestContain
from kallikrein.match_result import MatchResult, ContainsMatchResult, SimpleMatchResult
from kallikrein.matcher import BoundMatcher

from amino import Boolean, List
from amino.boolean import false

A = TypeVar('A')


def kn(vim: NvimApi, f: Callable[..., NvimIO[A]], *a: Any, **kw: Any) -> Expectable:
    return kf(lambda: f(*a, **kw).result(vim))


def kns(vim: NvimApi, f: Callable[..., NvimIO[A]], *a: Any, **kw: Any) -> Expectable:
    return kf(lambda: f(*a, **kw).run_s(vim))


class PredContainNResult(PredContain, tpe=NResult):

    def check(self, exp: NResult[A], target: A) -> Boolean:
        return Boolean(isinstance(exp, NSuccess) and exp.value == target)


class NestContainNResult(NestContain, tpe=NResult):

    def match(self, exp: NResult[A], target: BoundMatcher[A]) -> MatchResult[A]:
        return (
            target.evaluate(exp.value)
            if isinstance(exp, NSuccess) else
            SimpleMatchResult(false, List('{exp} is not NSuccess'))
        )

    def wrap(self, name: str, exp: NResult[A], nested: MatchResult[A]) -> MatchResult[A]:
        return ContainsMatchResult(name, exp, nested)


__all__ = ('kn',)
