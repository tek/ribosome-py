import inspect

from kallikrein import k, Expectation
from kallikrein.matchers.either import be_right

from amino import do
from amino.do import Do

from ribosome.nvim import NvimIO, NvimFacade


class NvimIoSpec:
    '''
    suspend $suspend
    delay $delay
    suspend flat_map $suspend_flat_map
    stack safety $stack
    frame $frame
    '''

    def suspend(self) -> Expectation:
        def f(v: NvimFacade) -> NvimIO[int]:
            return NvimIO.pure(7)
        return k(NvimIO.suspend(f).attempt(None)).must(be_right(7))

    def delay(self) -> Expectation:
        def f(v: NvimFacade) -> int:
            return 7
        return k(NvimIO.delay(f).attempt(None)).must(be_right(7))

    def suspend_flat_map(self) -> Expectation:
        def h(a: int) -> NvimIO[int]:
            return NvimIO.pure(a + 2)
        def g(a: int) -> NvimIO[int]:
            return NvimIO.suspend(lambda v, b: h(b), a + 1)
        def f(v: NvimFacade) -> NvimIO[int]:
            return NvimIO.pure(7)
        return k(NvimIO.suspend(f).flat_map(g).flat_map(h).attempt(None)).must(be_right(12))

    def stack(self) -> Expectation:
        @do(NvimIO[int])
        def run() -> Do:
            a = 0
            for i in range(1000):
                a = yield NvimIO.pure(a + 1)
        return k(run().attempt(None)).must(be_right(1000))

    def frame(self) -> Expectation:
        @do(NvimIO[int])
        def sub(a: int) -> Do:
            yield NvimIO.pure(a + 5)
            yield NvimIO.suspend(lambda v: asdf)
            yield NvimIO.pure(a + 5)
        @do(NvimIO[int])
        def run() -> Do:
            yield NvimIO.pure(1)
            x = yield sub(5)
            yield NvimIO.pure(x)
        result = run().result(None)
        return k(1) == 1

__all__ = ('NvimIoSpec',)
