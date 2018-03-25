from kallikrein import k, Expectation, kf
from kallikrein.matchers.either import be_right

from amino import do, List, Map, Right, Nil
from amino.do import Do
from amino.test.spec import SpecBase

from ribosome.nvim.api.data import NvimApi, StrictNvimApi
from ribosome.nvim.io import NvimIO, N


vars = dict(a=1)


def handler(vim: StrictNvimApi, method: str, args: List[str]) -> None:
    return Right(((args.head | 9) + 2, vim.copy(vars=vars)))


vim = StrictNvimApi('test', Map(), handler)


class NvimIoSpec(SpecBase):
    '''
    suspend $suspend
    delay $delay
    suspend flat_map $suspend_flat_map
    stack safety $stack
    request $request
    bind on request $request_bind
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

    def request(self) -> Expectation:
        return k(N.request('blub', Nil).run_s(vim).vars) == vars

    def request_bind(self) -> Expectation:
        @do(NvimIO[int])
        def run() -> Do:
            a = yield N.request('blub', List(5))
            b = yield N.pure(a + 1)
            return b + 23
        return kf(lambda: run().run_s(vim).vars) == vars


__all__ = ('NvimIoSpec',)
