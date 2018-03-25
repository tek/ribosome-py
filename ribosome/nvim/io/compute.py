import inspect
from traceback import FrameSummary
from typing import TypeVar, Callable, Any, Generic, Union, Tuple

from amino.tc.base import F
from amino import Either, __, Left, List, options, Nil, Do
from amino.state import State
from amino.func import tailrec
from amino.do import do
from amino.dat import ADT
from amino.util.trace import callsite_source
from amino.dispatch import PatMat

from ribosome.nvim.api.data import NvimApi
from ribosome.nvim.io.trace import NvimIOException
from ribosome.nvim.io.data import NFatal, NResult, NSuccess, NError

A = TypeVar('A')
B = TypeVar('B')
C = TypeVar('C')


class NvimIO(Generic[A], F[A], ADT['NvimIO'], implicits=True, imp_mod='ribosome.nvim.io.tc', imp_cls='NvimIOInstances'):
    debug = options.io_debug.exists

    def __init__(self, frame=None) -> None:
        self.frame = frame or inspect.currentframe()

    def run(self, vim: NvimApi) -> State[NvimApi, A]:
        return eval_nvim_io(self).run(vim).value

    def run_s(self, vim: NvimApi) -> State[NvimApi, A]:
        return eval_nvim_io(self).run_s(vim).value

    def result(self, vim: NvimApi) -> NResult[A]:
        try:
            return eval_nvim_io(self).run_a(vim).value
        except NvimIOException as e:
            return NFatal(e)

    def either(self, vim: NvimApi) -> Either[NvimIOException, A]:
        try:
            return self.run(vim).to_either
        except NvimIOException as e:
            return Left(e)

    def unsafe(self, vim: NvimApi) -> A:
        return self.either(vim).get_or_raise()

    def recover(self, f: Callable[[Exception], B]) -> 'NvimIO[B]':
        return NvimIO.delay(self.either).map(__.value_or(f))

    def recover_with(self, f: Callable[[Exception], 'NvimIO[B]']) -> 'NvimIO[B]':
        return NvimIO.delay(self.either).flat_map(__.map(NvimIO.pure).value_or(f))

    # FIXME use NResult
    @do('NvimIO[A]')
    def ensure(self, f: Callable[[Either[Exception, A]], 'NvimIO[None]']) -> Do:
        result = yield NvimIO.delay(self.either)
        yield f(result)
        yield NvimIO.from_either(result)

    def effect(self, f: Callable[[A], Any]) -> 'NvimIO[A]':
        def wrap(vim: NvimApi) -> A:
            ret = self.run(vim)
            f(ret)
            return ret
        return NvimIO.delay(wrap)

    __mod__ = effect

    def error_effect(self, f: Callable[[Exception], None]) -> 'NvimIO[A]':
        return self.ensure(lambda a: NvimIO.delay(lambda vim: a.leffect(f)))

    def error_effect_f(self, f: Callable[[Exception], 'NvimIO[None]']) -> 'NvimIO[A]':
        return self.ensure(lambda a: NvimIO.suspend(lambda vim: a.cata(f, NvimIO.pure)))

    @property
    def callsite_l1(self) -> str:
        return callsite_source(self.frame)[0][0]


class NvimIOSuspend(Generic[A], NvimIO[A]):

    def __init__(self, thunk: Callable[[NvimApi], Tuple[NvimIO[A], NvimApi]], frame: FrameSummary=None) -> None:
        super().__init__(frame)
        self.thunk = thunk


class NvimIOBind(Generic[A, B], NvimIO[B]):

    def __init__(
            self,
            thunk: Callable[[NvimApi], Tuple[NvimIO[A], NvimApi]],
            f: Callable[[A], NvimIO[B]],
            frame: FrameSummary,
    ) -> None:
        super().__init__(frame)
        self.thunk = thunk
        self.f = f


class NvimIOPure(Generic[A], NvimIO[A]):

    def __init__(self, value: A) -> None:
        super().__init__()
        self.value = value


class NvimIOComputePure(Generic[A], NvimIO[A]):

    def __init__(self, value: A, vim: NvimApi) -> None:
        super().__init__()
        self.value = value
        self.vim = vim


class NvimIORequest(Generic[A], NvimIO[A]):

    def __init__(self, method: str, args: List[str], frame: FrameSummary=None) -> None:
        super().__init__(frame)
        self.method = method
        self.args = args

    def req(self, vim: NvimApi) -> NvimIO[A]:
        return (
            vim.request(self.method, self.args)
            .map2(lambda result, updated_vim: NvimIOSuspend(lambda v1: (NvimIOPure(result), updated_vim)))
            .value_or(NvimIOError)
        )


class NvimIOError(Generic[A], NvimIO[A]):

    def __init__(self, error: str) -> None:
        self.error = error


class NvimIOFatal(Generic[A], NvimIO[A]):

    def __init__(self, exception: Exception) -> None:
        self.exception = exception


class flat_map_nvim_io(PatMat[Callable[[A], NvimIO[B]], NvimIO[B]], alg=NvimIO):

    def __init__(self, f: Callable[[A], NvimIO[B]]) -> None:
        self.f = f

    def nvim_io_pure(self, io: NvimIOPure[A]) -> NvimIO[B]:
        def thunk(vim: NvimApi) -> NvimIO[B]:
            return self.f(io.value), vim
        return NvimIOSuspend(thunk)

    def nvim_io_compute_pure(self, io: NvimIOComputePure[A]) -> NvimIO[B]:
        def thunk(vim: NvimApi) -> NvimIO[B]:
            return self.f(io.value), vim
        return NvimIOSuspend(thunk)

    def nvim_io_suspend(self, io: NvimIOSuspend[A]) -> NvimIO[B]:
        return NvimIOBind(io.thunk, self.f, io.frame)

    def nvim_io_request(self, io: NvimIORequest[A]) -> NvimIO[B]:
        def thunk(vim: NvimApi) -> NvimIO[B]:
            return io.req(vim), vim
        return NvimIOBind(thunk, self.f, io.frame)

    def nvim_io_bind(self, io: NvimIOBind[C, A]) -> NvimIO[B]:
        def bs(vim: NvimApi) -> NvimIO[C]:
            return NvimIOBind(self.thunk, lambda a: io.f(a).flat_map(self.f)), vim
        return NvimIOSuspend(bs)

    def nvim_io_error(self, io: NvimIOError[A]) -> NvimIO[B]:
        return io

    def nvim_io_fatal(self, io: NvimIOFatal[A]) -> NvimIO[B]:
        return io


EvalRes = Tuple[bool, Union[Tuple[NResult[A], NvimApi], Tuple[NvimIO[A], NvimApi]]]


# class `RecPatMat` that handles recursion internally. A call to the function returns `PatMatData(True, args)` and its
# `evaluate` method does the tailrec call.
# If a different type is returned, it is the result. Could also have a `PatMatResult` type for safety.
# Could also use `yield` for recursion, `return` for result.
class eval_nvim_io_1(PatMat[NvimIO[A], NResult[A]], alg=NvimIO):

    def __init__(self, vim: NvimApi) -> None:
        self.vim = vim

    def nvim_io_pure(self, io: NvimIOPure[A]) -> EvalRes:
        return False, (NSuccess(io.value), self.vim)

    def nvim_io_compute_pure(self, io: NvimIOComputePure[A]) -> EvalRes:
        return False, (NSuccess(io.value), self.vim)

    def nvim_io_suspend(self, io: NvimIOSuspend[A]) -> EvalRes:
        return True, io.thunk(self.vim)

    def nvim_io_request(self, io: NvimIORequest[A]) -> EvalRes:
        return True, (io.req(self.vim), self.vim)

    def nvim_io_bind(self, io: NvimIOBind[B, A]) -> EvalRes:
        try:
            step, vim = io.thunk(self.vim)
        except NvimIOException as e:
            raise e
        except Exception as e:
            raise NvimIOException('', Nil, e, io.frame)
        else:
            return True, (step.flat_map(io.f), vim)

    def nvim_io_error(self, io: NvimIOError[A]) -> EvalRes:
        return False, (NError(io.error), self.vim)

    def nvim_io_fatal(self, io: NvimIOFatal[A]) -> EvalRes:
        return False, (NFatal(io.exception), self.vim)


@do(State[NvimApi, A])
def eval_nvim_io(io: NvimIO[A]) -> Do:
    @tailrec
    def loop(t: NvimIO[A], vim: NvimApi) -> Union[Tuple[bool, A], Tuple[bool, Tuple[Union[A, NvimIO[A]]]]]:
        return eval_nvim_io_1(vim)(t)
    vim = yield State.get()
    a, vim1 = loop(io, vim)
    yield State.set(vim1)
    return a


__all__ = ('NvimIO',)
