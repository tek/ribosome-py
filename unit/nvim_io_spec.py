from typing import Tuple, Any

from kallikrein import k, Expectation
from kallikrein.matchers.either import be_right
from kallikrein.matchers import contain

from amino import do, List, Map, Right, Nil, Either
from amino.do import Do
from amino.test.spec import SpecBase

from ribosome.nvim.api.data import NvimApi, StrictNvimApi
from ribosome.nvim.io.compute import NvimIO
from ribosome.test.klk import kn
from ribosome.nvim.io.api import N
from ribosome.nvim.io.data import NError


vars = dict(a=1)


def handler(vim: StrictNvimApi, method: str, args: List[str], sync: bool) -> Either[List[str], Tuple[NvimApi, Any]]:
    return Right((vim.copy(vars=vars), (args.head | 9) + 2))


vim = StrictNvimApi.cons('test', request_handler=handler)


def handler_a(vim: StrictNvimApi, method: str, args: List[str], sync: bool) -> Either[List[str], Tuple[NvimApi, Any]]:
    return Right((vim, sync))


vim_async = StrictNvimApi.cons('test', request_handler=handler_a)


class NvimIoSpec(SpecBase):
    '''
    suspend $suspend
    delay $delay
    suspend flat_map $suspend_flat_map
    stack safety $stack
    request $request
    bind on request $request_bind
    preserve resource state in `recover` $recover
    recover an exception with `recover_failure` $recover_failure
    execute an effect after error $ensure_failure
    async request $async_request
    bind on async request $async_request_bind
    '''

    def suspend(self) -> Expectation:
        def f(v: NvimApi) -> NvimIO[int]:
            return N.pure(7)
        return k(N.suspend(f).either(None)).must(be_right(7))

    def delay(self) -> Expectation:
        def f(v: NvimApi) -> int:
            return 7
        return k(N.delay(f).either(None)).must(be_right(7))

    def suspend_flat_map(self) -> Expectation:
        def h(a: int) -> NvimIO[int]:
            return N.pure(a + 2)
        def g(a: int) -> NvimIO[int]:
            return N.suspend(lambda v, b: h(b), a + 1)
        def f(v: NvimApi) -> NvimIO[int]:
            return N.pure(7)
        return k(N.suspend(f).flat_map(g).flat_map(h).either(None)).must(be_right(12))

    def stack(self) -> Expectation:
        @do(NvimIO[int])
        def run(a: int) -> Do:
            b = yield N.pure(a + 1)
            if b < 1000:
                yield run(b)
        return kn(vim, run, 1).must(contain(1000))

    def request(self) -> Expectation:
        return k(N.request('blub', Nil).run_s(vim).vars) == vars

    def request_bind(self) -> Expectation:
        @do(NvimIO[int])
        def run() -> Do:
            ae = yield N.request('blub', List(5))
            a = yield N.e(ae)
            b = yield N.suspend(lambda v: N.pure(a + 1))
            c = yield N.delay(lambda v: b + 3)
            return c + 23
        updated_vim, result = run().run(vim)
        return (
            (k(updated_vim.vars) == vars) &
            (k(result).must(contain(34))) &
            (k(updated_vim.request_log) == List(('blub', List(5))))
        )

    def recover(self) -> Expectation:
        @do(NvimIO[int])
        def run() -> Do:
            a = yield N.recover_error(N.error('booh'), lambda e: Right(1))
            b = yield N.suspend(lambda v: N.pure(a + 1))
            c = yield N.delay(lambda v: b + 3)
            return c + 23
        updated_vim, result = run().run(vim)
        return k(result).must(contain(28))

    def recover_failure(self) -> Expectation:
        def boom(v: NvimApi) -> NvimIO[int]:
            raise Exception('boom')
        @do(NvimIO[int])
        def run() -> Do:
            a = yield N.recover_failure(N.delay(boom), lambda e: Right(1))
            return a + 1
        result = run().run_a(vim)
        return k(result).must(contain(2))

    def ensure_failure(self) -> Expectation:
        x = 1
        def inc(v: NvimApi) -> None:
            nonlocal x
            x = 2
        run = N.ensure_failure(N.error('booze'), lambda a: N.delay(inc))
        result = run.run_a(vim)
        return (k(x) == 2) & (k(result) == NError('booze'))

    def async_request(self) -> Expectation:
        return k(N.request('blub', Nil).async.run_a(vim_async)).must(contain(be_right(False)))

    def async_request_bind(self) -> Expectation:
        @do(NvimIO[int])
        def req() -> Do:
            yield N.pure(1)
            ae = yield N.request('blub', List(5))
            yield N.e(ae)
        @do(NvimIO[int])
        def level1() -> Do:
            yield N.pure(1)
            yield req()
        @do(NvimIO[int])
        def run() -> Do:
            yield N.pure(1)
            first = yield level1().async
            ae = yield N.request('blub', List(1))
            second = yield N.e(ae)
            return first, second
        return kn(vim_async, run).must(contain((False, True)))


__all__ = ('NvimIoSpec',)
