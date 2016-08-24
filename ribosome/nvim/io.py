from typing import TypeVar, Callable, Any, Generic

from tryp import F

from amino import Either, Right, Left

from ribosome.nvim.components import NvimComponent

A = TypeVar('A')
B = TypeVar('B')


class NvimIO(Generic[A]):

    def __init__(self, apply: Callable[[NvimComponent], A]) -> None:
        self._apply = apply

    def unsafe_perform_io(self, vim) -> Either[Exception, A]:
        try:
            return Right(self._apply(vim))
        except Exception as e:
            return Left(e)

    def flat_map(self, f: Callable[[A], 'NvimIO[B]']):
        g = lambda v: f(self._apply(v))._apply(v)
        return NvimIO(g)

    __floordiv__ = flat_map

    def map(self, f: Callable[[A], B]):
        return NvimIO(F(self._apply) >> f)

    __truediv__ = map

    def effect(self, f: Callable[[A], Any]):
        def wrap(v):
            ret = self._apply(v)
            f(ret)
            return ret
        return NvimIO(wrap)

    __mod__ = effect


__all__ = ('NvimIO',)
