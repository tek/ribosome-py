from kallikrein import k, Expectation
from kallikrein.matchers.either import be_right

from amino import do, List, Map, Right
from amino.do import Do
from amino.test.spec import SpecBase

from ribosome.nvim.api.data import NvimApi, StrictNvimApi
from ribosome.nvim import NvimIO


class NvimIoSpec(SpecBase):
    '''
    suspend $suspend
    delay $delay
    suspend flat_map $suspend_flat_map
    stack safety $stack
    frame $frame
    request handler $request_handler
    '''

    def suspend(self) -> Expectation:
        def f(v: NvimApi) -> NvimIO[int]:
            return NvimIO.pure(7)
        return k(NvimIO.suspend(f).attempt(None)).must(be_right(7))

    def delay(self) -> Expectation:
        def f(v: NvimApi) -> int:
            return 7
        return k(NvimIO.delay(f).attempt(None)).must(be_right(7))

    def suspend_flat_map(self) -> Expectation:
        def h(a: int) -> NvimIO[int]:
            return NvimIO.pure(a + 2)
        def g(a: int) -> NvimIO[int]:
            return NvimIO.suspend(lambda v, b: h(b), a + 1)
        def f(v: NvimApi) -> NvimIO[int]:
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

    def request_handler(self) -> Expectation:
        def handler(vim: StrictNvimApi, method: str, args: List[str]) -> None:
            return Right(((args.head | 9) + 2, vim.copy(vars=dict(a=1))))
        @do(NvimIO[int])
        def run() -> Do:
            a = yield NvimIO.request('blub', List(5))
            b = yield NvimIO.pure(a + 1)
            return b + 23
        vim = StrictNvimApi('test', Map(), handler)
        vim1, result = run().run(vim)
        print(result)
        print(vim1.vars)
        return k(1) == 1


__all__ = ('NvimIoSpec',)
