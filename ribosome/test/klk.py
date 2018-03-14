from typing import TypeVar

from ribosome.nvim import NvimIO, NvimFacade
from ribosome.nvim.io import NResult, NSuccess

from kallikrein import kf
from kallikrein.expectable import Expectable
from kallikrein.matchers.contain import PredContain, NestContain
from kallikrein.match_result import MatchResult, ContainsMatchResult, SimpleMatchResult
from kallikrein.matcher import BoundMatcher

from amino import Boolean, List
from amino.boolean import false

A = TypeVar('A')


def kn(io: NvimIO[A], vim: NvimFacade) -> Expectable:
    return kf(io.result, vim)


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
        return List.wrap([target.evaluate(e) for e in exp])

    def wrap(self, name: str, exp: NResult[A], nested: MatchResult[A]) -> MatchResult[A]:
        return ContainsMatchResult(name, exp, nested)


__all__ = ('kn',)
