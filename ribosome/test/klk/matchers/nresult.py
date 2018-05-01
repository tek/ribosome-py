from typing import TypeVar, Generic, Union, Callable

from kallikrein.matcher import BoundMatcher, StrictMatcher
from kallikrein.matchers.typed import ChainTyped, have_type
from kallikrein.matchers import contain
from kallikrein.matchers.contain import PredContain, NestContain
from kallikrein.match_result import MatchResult, ContainsMatchResult

from amino import Boolean
from amino.case import Case

from ribosome.nvim.io.data import NResult, NSuccess, NError, NFatal

A = TypeVar('A')
B = TypeVar('B')
Result = Union[A, str, Exception]


class apply_nresult(Generic[A, B], Case[NResult[A], B], alg=NResult):

    def __init__(self, target: Callable[[Result], B]) -> None:
        self.target = target

    def nsuccess(self, result: NSuccess[A]) -> B:
        return self.target(result.value)

    def nerror(self, result: NError[A]) -> B:
        return self.target(result.error)

    def nfatal(self, result: NFatal[A]) -> B:
        return self.target(result.exception)


class PredContainNResult(PredContain, tpe=NResult):

    def check(self, exp: NResult[A], target: Result) -> Boolean:
        def match(a: Result) -> Boolean:
            return Boolean(a == target)
        apply: apply_nresult[A, Boolean] = apply_nresult(match)
        return apply(exp)


class NestContainNResult(NestContain, tpe=NResult):

    def match(self, exp: NResult[A], target: BoundMatcher[Result]) -> MatchResult[Result]:
        apply: apply_nresult[A, MatchResult[Result]] = apply_nresult(target.evaluate)
        return apply(exp)

    def wrap(self, name: str, exp: NResult[A], nested: MatchResult[A]) -> MatchResult[A]:
        return ContainsMatchResult(name, exp, nested)


class ChainTypedNResult(ChainTyped, tpe=NResult):

    def chain(self, matcher: StrictMatcher, other: Union[A, BoundMatcher]) -> BoundMatcher:
        return matcher & contain(other)


nsuccess = have_type(NSuccess)
nerror = have_type(NError)
nfatal = have_type(NFatal)

__all__ = ('nsuccess', 'nerror', 'nfatal')
