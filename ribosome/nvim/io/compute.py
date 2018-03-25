from traceback import FrameSummary
from typing import TypeVar, Callable, Generic, Union, Tuple

from amino.tc.base import F
from amino import Either, List, options, Do
from amino.state import State
from amino.func import tailrec
from amino.do import do
from amino.dat import ADT
from amino.case import Case, CaseRec, Term

from ribosome.nvim.api.data import NvimApi
from ribosome.nvim.io.trace import NvimIOException
from ribosome.nvim.io.data import NFatal, NResult, NSuccess, NError, Thunk, eval_thunk

A = TypeVar('A')
B = TypeVar('B')
C = TypeVar('C')


class NvimIO(Generic[A], F[A], ADT['NvimIO[A]'], implicits=True, imp_mod='ribosome.nvim.io.tc'):
    debug = options.io_debug.exists

    def eval(self) -> State[NvimApi, A]:
        return eval_nvim_io(self)

    def run(self, vim: NvimApi) -> Tuple[NvimApi, NResult[A]]:
        return self.eval().run(vim).value

    def run_s(self, vim: NvimApi) -> NvimApi:
        return self.eval().run_s(vim).value

    def result(self, vim: NvimApi) -> NResult[A]:
        try:
            return self.eval().run_a(vim).value
        except NvimIOException as e:
            return NFatal(e)

    def either(self, vim: NvimApi) -> Either[NvimIOException, A]:
        return self.result(vim).to_either

    def unsafe(self, vim: NvimApi) -> A:
        return self.either(vim).get_or_raise()


class NvimIOPure(Generic[A], NvimIO[A]):

    def __init__(self, value: A) -> None:
        self.value = value


class NvimIORequest(Generic[A], NvimIO[A]):

    def __init__(self, method: str, args: List[str]) -> None:
        self.method = method
        self.args = args


class NvimIOSuspend(Generic[A], NvimIO[A]):

    @staticmethod
    def cons(thunk: Callable[[NvimApi], Tuple[NvimApi, NvimIO[A]]]) -> 'NvimIOSuspend[A]':
        return NvimIOSuspend(Thunk.cons(thunk))

    def __init__(self, thunk: Thunk[NvimApi, NvimIO[A]]) -> None:
        self.thunk = thunk


class NvimIOBind(Generic[A, B], NvimIO[B]):

    def __init__(
            self,
            thunk: Thunk[NvimApi, NvimIO[A]],
            kleisli: Callable[[A], NvimIO[B]],
    ) -> None:
        self.thunk = thunk
        self.kleisli = kleisli


class NvimIOError(Generic[A], NvimIO[A]):

    def __init__(self, error: str) -> None:
        self.error = error


class NvimIOFatal(Generic[A], NvimIO[A]):

    def __init__(self, exception: Exception) -> None:
        self.exception = exception


def execute_nvim_request(vim: NvimApi, io: NvimIORequest[A]) -> NvimIO[A]:
    return (
        vim.request(io.method, io.args)
        .map2(lambda updated_vim, result: NvimIOSuspend.cons(lambda v1: (updated_vim, NvimIOPure(result))))
        .value_or(NvimIOError)
    )


class flat_map_nvim_io(Case[Callable[[A], NvimIO[B]], NvimIO[B]], alg=NvimIO):

    def __init__(self, f: Callable[[A], NvimIO[B]]) -> None:
        self.f = f

    def nvim_io_pure(self, io: NvimIOPure[A]) -> NvimIO[B]:
        def thunk(vim: NvimApi) -> NvimIO[B]:
            return vim, self.f(io.value)
        return NvimIOSuspend.cons(thunk)

    def nvim_io_suspend(self, io: NvimIOSuspend[A]) -> NvimIO[B]:
        return NvimIOBind(io.thunk, self.f)

    def nvim_io_request(self, io: NvimIORequest[A]) -> NvimIO[B]:
        def thunk(vim: NvimApi) -> NvimIO[B]:
            return vim, execute_nvim_request(vim, io)
        return NvimIOBind(Thunk.cons(thunk), self.f)

    def nvim_io_bind(self, io: NvimIOBind[C, A]) -> NvimIO[B]:
        def thunk(vim: NvimApi) -> NvimIO[C]:
            return vim, NvimIOBind(io.thunk, lambda a: io.kleisli(a).flat_map(self.f))
        return NvimIOSuspend.cons(thunk)

    def nvim_io_error(self, io: NvimIOError[A]) -> NvimIO[B]:
        return io

    def nvim_io_fatal(self, io: NvimIOFatal[A]) -> NvimIO[B]:
        return io


EvalRes = Tuple[bool, Union[Tuple[NResult[A], NvimApi], Tuple[NvimIO[A], NvimApi]]]


class eval_step(CaseRec[NvimIO[A], NResult[A]], alg=NvimIO):

    def __init__(self, vim: NvimApi) -> None:
        self.vim = vim

    def nvim_io_pure(self, io: NvimIOPure[A]) -> EvalRes:
        return Term((self.vim, NSuccess(io.value)))

    def nvim_io_request(self, io: NvimIORequest[A]) -> EvalRes:
        next = execute_nvim_request(self.vim, io)
        return eval_step(self.vim)(next)

    def nvim_io_suspend(self, io: NvimIOSuspend[A]) -> EvalRes:
        vim, next = eval_thunk(self.vim, io.thunk)
        return eval_step(vim)(next)

    def nvim_io_bind(self, io: NvimIOBind[B, A]) -> EvalRes:
        vim, next = eval_thunk(self.vim, io.thunk)
        return eval_step(vim)(next.flat_map(io.kleisli))

    def nvim_io_error(self, io: NvimIOError[A]) -> EvalRes:
        return Term((self.vim, NError(io.error)))

    def nvim_io_fatal(self, io: NvimIOFatal[A]) -> EvalRes:
        return Term((self.vim, NFatal(io.exception)))


@do(State[NvimApi, A])
def eval_nvim_io(io: NvimIO[A]) -> Do:
    @tailrec
    def loop(vim: NvimApi, t: NvimIO[A]) -> Union[Tuple[bool, A], Tuple[bool, Tuple[Union[A, NvimIO[A]]]]]:
        return eval_step(vim)(t)
    vim = yield State.get()
    updated_vim, result = eval_step(vim)(io).eval()
    yield State.set(updated_vim)
    return result


__all__ = ('NvimIO',)
