import abc
import inspect
from traceback import FrameSummary
from typing import TypeVar, Callable, Any, Generic, Union, Tuple, Type
from threading import Thread

from msgpack import ExtType

from neovim.api import NvimError

from amino.tc.base import ImplicitInstances, F, TypeClass, tc_prop, ImplicitsMeta
from amino.lazy import lazy
from amino.tc.monad import Monad
from amino import Either, __, IO, Maybe, Left, Eval, List, Right, options, Nil, Do, Just, Try, Lists, curried
from amino.state import tcs, StateT, State, EitherState
from amino.func import CallByName, tailrec
from amino.do import do
from amino.dat import ADT, ADTMeta
from amino.io import IOExceptionBase
from amino.util.trace import default_internal_packages, cframe, callsite_source
from amino.util.string import decode
from amino.dispatch import PatMat

from ribosome.nvim.api.data import NvimApi

A = TypeVar('A')
B = TypeVar('B')
C = TypeVar('C')
S = TypeVar('S')


class NvimIOException(IOExceptionBase):

    @property
    def desc(self) -> str:
        return 'NvimIO exception'

    @property
    def internal_packages(self) -> Maybe[List[str]]:
        return Just(default_internal_packages.cons('ribosome.nvim'))


class NvimIOInstances(ImplicitInstances):

    @lazy
    def _instances(self) -> 'amino.map.Map':
        from amino.map import Map
        return Map({Monad: NvimIOMonad()})


class NResult(Generic[A], ADT['NvimIOResult[A]']):

    @abc.abstractproperty
    def to_either(self) -> Either[Exception, A]:
        ...


class NSuccess(Generic[A], NResult[A]):

    def __init__(self, value: A) -> None:
        self.value = value

    @property
    def to_either(self) -> Either[Exception, A]:
        return Right(self.value)


class NError(Generic[A], NResult[A]):

    def __init__(self, error: str) -> None:
        self.error = error

    @property
    def to_either(self) -> Either[Exception, A]:
        return Left(Exception(self.error))


class NFatal(Generic[A], NResult[A]):

    def __init__(self, exception: Exception) -> None:
        self.exception = exception

    @property
    def to_either(self) -> Either[Exception, A]:
        return Left(self.exception)


class NvimIOMeta(ADTMeta):

    @property
    def unit(self) -> 'NvimIO':
        return NvimIO.pure(None)


class NvimIO(Generic[A], F[A], ADT['NvimIO'], implicits=True, imp_mod='ribosome.nvim.io', imp_cls='NvimIOInstances',
             metaclass=NvimIOMeta):
    debug = options.io_debug.exists

    @staticmethod
    def wrap_either(f: Callable[[NvimApi], Either[B, A]], frame: FrameSummary=None) -> 'NvimIO[A]':
        return NvimIO.suspend(lambda a: f(a).cata(NvimIO.error, NvimIO.pure), _frame=frame)

    @staticmethod
    def from_either(e: Either[str, A], frame: FrameSummary=None) -> 'NvimIO[A]':
        return e.cata(NvimIO.error, NvimIO.pure)

    @staticmethod
    def e(e: Either[str, A], frame: FrameSummary=None) -> 'NvimIO[A]':
        return NvimIO.from_either(e, frame)

    @staticmethod
    def from_maybe(e: Maybe[A], error: CallByName, frame: FrameSummary=None) -> 'NvimIO[A]':
        return NvimIO.from_either(e.to_either(error), frame)

    @staticmethod
    def m(e: Maybe[A], error: CallByName, frame: FrameSummary=None) -> 'NvimIO[A]':
        return NvimIO.from_maybe(e, error, frame)

    @staticmethod
    def cmd_sync(cmdline: str, verbose=False) -> 'NvimIO[str]':
        return NvimIO.wrap_either(__.cmd_sync(cmdline, verbose=verbose))

    @staticmethod
    def cmd(cmdline: str, verbose=False) -> 'NvimIO[str]':
        return NvimIO.wrap_either(__.cmd(cmdline, verbose=verbose))

    @staticmethod
    def call(name: str, *args: Any, **kw: Any) -> 'NvimIO[A]':
        return NvimIO.wrap_either(__.call(name, *args, **kw))

    @staticmethod
    def call_once_defined(name: str, *args: Any, **kw: Any) -> 'NvimIO[A]':
        return NvimIO.wrap_either(__.call_once_defined(name, *args, **kw))

    @staticmethod
    def exception(exc: Exception) -> 'NvimIO[A]':
        return NvimIOFatal(exc)

    @staticmethod
    def failed(msg: str) -> 'NvimIO[A]':
        return NvimIO.exception(Exception(msg))

    @staticmethod
    def error(msg: str) -> 'NvimIO[A]':
        return NvimIOError(msg)

    @staticmethod
    def from_io(io: IO[A]) -> 'NvimIO[A]':
        return NvimIO.delay(lambda a: io.attempt.get_or_raise())

    # @staticmethod
    # def fork(f: Callable[[NvimApi], None]) -> 'NvimIO[None]':
    #     return NvimIO.delay(lambda v: Thread(target=f, args=(v,)).start())

    @staticmethod
    def delay(f: Callable[..., A], *a: Any, **kw: Any) -> 'NvimIO[A]':
        def g(vim: NvimApi) -> A:
            return NvimIOComputePure(f(vim, *a, **kw), vim)
        return NvimIOSuspend(g)


    @staticmethod
    def request(method: str, args: List[str]) -> 'NvimIO[A]':
        return NvimIORequest(method, args)

    @staticmethod
    def simple(f: Callable[..., A], *a, **kw) -> 'NvimIO[A]':
        return NvimIO.delay(lambda v: f(*a, **kw))

    @staticmethod
    def suspend(f: Callable[..., 'NvimIO[A]'], *a: Any, _frame: FrameSummary=None, **kw: Any) -> 'NvimIO[A]':
        def g(vim: NvimApi) -> NvimIO[A]:
            return f(vim, *a, **kw)
        return NvimIOSuspend(g, _frame)

    @staticmethod
    def pure(a: A) -> 'NvimIO[A]':
        return NvimIOPure(a)

    @staticmethod
    def read_tpe(cmd: str, tpe: Type[A], *args: Any) -> 'NvimIO[A]':
        return typechecked_request(cmd, tpe, *args)

    @staticmethod
    def read_cons(cmd: str, cons: Callable[[Any], Either[str, A]], *args: Any) -> 'NvimIO[A]':
        return data_cons_request(cmd, cons, *args)

    @staticmethod
    def read_ext(cmd: str, *args: Any) -> 'NvimIO[A]':
        return NvimIO.read_tpe(cmd, ExtType, *args)

    @staticmethod
    def write(cmd: str, *args: Any) -> 'NvimIO[A]':
        return nvim_request(cmd, *args).replace(None)

    def __init__(self, frame=None) -> None:
        self.frame = frame or inspect.currentframe()

    def flat_map(self, f: Callable[[A], 'NvimIO[B]']) -> 'NvimIO[B]':
        return flat_map_nvim_io(f)(self)

    def run(self, vim: NvimApi) -> State[NvimApi, A]:
        return eval_nvim_io(self).run(vim).value

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

    def attempt(self, vim: NvimApi) -> Either[NvimIOException, A]:
        return self.either(vim)

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
        def wrap(v: NvimApi) -> A:
            ret = self.run(v)
            f(ret)
            return ret
        return NvimIO.delay(wrap)

    __mod__ = effect

    def error_effect(self, f: Callable[[Exception], None]) -> 'NvimIO[A]':
        return self.ensure(lambda a: NvimIO.delay(lambda v: a.leffect(f)))

    def error_effect_f(self, f: Callable[[Exception], 'NvimIO[None]']) -> 'NvimIO[A]':
        return self.ensure(lambda a: NvimIO.suspend(lambda v: a.cata(f, NvimIO.pure)))

    @property
    def callsite_l1(self) -> str:
        return callsite_source(self.frame)[0][0]


class NvimIOSuspend(Generic[A], NvimIO[A]):

    def __init__(self, thunk: Callable[[NvimApi], Tuple[NvimIO[A], NvimApi]], frame: FrameSummary=None) -> None:
        super().__init__(frame)
        self.thunk = thunk


class NvimIOBindSuspend(Generic[A, B], NvimIO[B]):

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


class NvimIOComputeSuspend(Generic[A], NvimIO[A]):

    def __init__(self, thunk: Callable[[NvimApi], NvimIO[A]], vim: NvimApi) -> None:
        super().__init__()
        self.thunk = thunk
        self.vim = vim


class NvimIOComputeBindSuspend(Generic[A, B], NvimIO[B]):

    def __init__(self, thunk: Callable[[NvimApi], NvimIO[A]], f: Callable[[A], NvimIO[B]], vim: NvimApi) -> None:
        super().__init__()
        self.thunk = thunk
        self.f = f
        self.vim = vim


class NvimIORequest(Generic[A], NvimIO[A]):

    def __init__(self, method: str, args: List[str], frame: FrameSummary=None) -> None:
        super().__init__(frame)
        self.method = method
        self.args = args

    def req(self, vim: NvimApi) -> NvimIO[A]:
        r = vim.request(self.method, self.args)
        return r.cata(NvimIOError, lambda a: NvimIOComputePure(a[0], a[1]))


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
            return self.f(io.value)
        return NvimIOSuspend(thunk)

    def nvim_io_compute_pure(self, io: NvimIOComputePure[A]) -> NvimIO[B]:
        def thunk(vim: NvimApi) -> NvimIO[B]:
            return self.f(io.value)
        return NvimIOComputeSuspend(thunk, io.vim)

    def nvim_io_suspend(self, io: NvimIOSuspend[A]) -> NvimIO[B]:
        return NvimIOBindSuspend(io.thunk, self.f, io.frame)

    def nvim_io_compute_suspend(self, io: NvimIOComputeSuspend[A]) -> NvimIO[B]:
        return NvimIOComputeBindSuspend(io.thunk, self.f, io.frame, io.vim)

    def nvim_io_request(self, io: NvimIORequest[A]) -> NvimIO[B]:
        def thunk(v: NvimApi) -> NvimIO[B]:
            return io.req(v)
        return NvimIOBindSuspend(thunk, self.f, io.frame)

    def nvim_io_bind_suspend(self, io: NvimIOBindSuspend[C, A]) -> NvimIO[B]:
        def bs(vim: NvimApi) -> NvimIO[C]:
            return NvimIOBindSuspend(self.thunk, lambda a: io.f(a).flat_map(self.f), self.frame)
        return NvimIOSuspend(bs)

    def nvim_io_compute_bind_suspend(self, io: NvimIOComputeBindSuspend[C, A]) -> NvimIO[B]:
        def bs(vim: NvimApi) -> NvimIO[C]:
            return NvimIOComputeBindSuspend(self.thunk, lambda a: io.f(a).flat_map(self.f), vim)
        return NvimIOComputeSuspend(bs, io.vim)

    def nvim_io_error(self, io: NvimIOError[A]) -> NvimIO[B]:
        return

    def nvim_io_fatal(self, io: NvimIOFatal[A]) -> NvimIO[B]:
        return


# class `RecPatMat` that handles recursion internally. A call to the function returns `PatMatData(True, args)` and its
# `evaluate` method does the tailrec call.
# If a different type is returned, it is the result. Could also have a `PatMatResult` type for safety.
# Could also use `yield` for recursion, `return` for result.
class eval_nvim_io_1(PatMat[NvimIO[A], NResult[A]], alg=NvimIO):

    def __init__(self, vim: NvimApi) -> None:
        self.vim = vim

    def nvim_io_pure(self, io: NvimIOPure[A]) -> NResult[A]:
        return False, (NSuccess(io.value), self.vim)

    def nvim_io_compute_pure(self, io: NvimIOComputePure[A]) -> NvimIO[B]:
        return False, (NSuccess(io.value), io.vim)

    def nvim_io_suspend(self, io: NvimIOSuspend[A]) -> NResult[A]:
        return True, (io.thunk(self.vim), self.vim)

    def nvim_io_compute_suspend(self, io: NvimIOComputeSuspend[A]) -> NvimIO[B]:
        return True, (io.thunk(io.vim), io.vim)

    def nvim_io_request(self, io: NvimIORequest[A]) -> NResult[A]:
        raise Exception('req')
        return True, (io.step(self.vim), self.vim)

    def nvim_io_bind_suspend(self, io: NvimIOBindSuspend[B, A]) -> NResult[A]:
        try:
            step = io.thunk(self.vim)
        except NvimIOException as e:
            raise e
        except Exception as e:
            raise NvimIOException('', Nil, e, io.frame)
        try:
            return True, (step.flat_map(io.f), self.vim)
        except NvimIOException as e:
            raise e
        except Exception as e:
            raise NvimIOException('', Nil, e, step.frame)

    def nvim_io_compute_bind_suspend(self, io: NvimIOComputeBindSuspend[B, A]) -> NResult[A]:
        try:
            step = io.thunk(io.vim)
        except NvimIOException as e:
            raise e
        except Exception as e:
            raise NvimIOException('', Nil, e, io.frame)
        try:
            return True, (step.flat_map(io.f), io.vim)
        except NvimIOException as e:
            raise e
        except Exception as e:
            raise NvimIOException('', Nil, e, step.frame)

    def nvim_io_error(self, io: NvimIOError[A]) -> NResult[A]:
        return False, (NError(io.error), self.vim)

    def nvim_io_fatal(self, io: NvimIOFatal[A]) -> NResult[A]:
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


class NvimIOMonad(Monad[NvimIO]):

    def pure(self, a: A) -> NvimIO[A]:
        return NvimIO.pure(a)

    def flat_map(self, fa: NvimIO[A], f: Callable[[A], NvimIO[B]]) -> NvimIO[B]:
        return fa.flat_map(f)


def nvim_error_msg(exc: NvimError) -> str:
    return Try(lambda: decode(exc.args[0])) | str(exc)


@curried
def nvim_request_error(name: str, args: tuple, desc: str, error: Any) -> NvimIO[A]:
    msg = (nvim_error_msg(error.cause) if isinstance(error, NvimIOException) else str(error))
    return NvimIOError(f'{desc} in nvim request `{name}({Lists.wrap(args).join_comma})`: {msg}')


@decode.register(ExtType)
def decode_ext_type(a: ExtType) -> ExtType:
    return a


@do(NvimIO[Either[str, A]])
def nvim_nonfatal_request(name: str, *args: Any) -> Do:
    value = yield (
        NvimIO.request(name, Lists.wrap(args))
        .recover_with(nvim_request_error(name, args, 'fatal error'))
    )
    return value / decode


@do(NvimIO[A])
def nvim_request(name: str, *args: Any) -> Do:
    result = yield nvim_nonfatal_request(name, *args)
    yield NvimIO.from_either(result).recover_with(nvim_request_error(name, args, 'error'))


@do(NvimIO[A])
def typechecked_request(name: str, tpe: Type[A], *args: Any) -> Do:
    raw = yield nvim_request(name, *args)
    yield (
        NvimIO.pure(raw)
        if isinstance(raw, tpe) else
        NvimIO.error(f'invalid result type of request {name}{args}: {raw}')
    )


@do(NvimIO[A])
def data_cons_request(name: str, cons: Callable[[Any], Either[str, A]], *args: Any) -> Do:
    raw = yield nvim_request(name, *args)
    yield NvimIO.from_either(cons(raw))


@do(NvimIO[Either[str, A]])
def data_cons_request_nonfatal(name: str, cons: Callable[[Either[str, Any]], Either[str, A]], *args: Any) -> Do:
    raw = yield nvim_nonfatal_request(name, *args)
    return cons(raw)


class NvimIOState(Generic[S, A], StateT[NvimIO, S, A], tpe=NvimIO):

    @staticmethod
    def io(f: Callable[[NvimApi], A]) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(NvimIO.delay(f))

    @staticmethod
    def delay(f: Callable[[NvimApi], A]) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(NvimIO.delay(f))

    @staticmethod
    def suspend(f: Callable[[NvimApi], NvimIO[A]]) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(NvimIO.suspend(f))

    @staticmethod
    def from_io(io: IO[A]) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(NvimIO.wrap_either(lambda v: io.attempt))

    @staticmethod
    def from_id(st: State[S, A]) -> 'NvimIOState[S, A]':
        return st.transform_f(NvimIOState, lambda s: NvimIO.pure(s.value))

    @staticmethod
    def from_maybe(a: Maybe[A], err: CallByName) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(NvimIO.from_maybe(a, err))

    @staticmethod
    def from_either(e: Either[str, A]) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(NvimIO.from_either(e))

    @staticmethod
    def from_either_state(st: EitherState[S, A]) -> 'NvimIOState[S, A]':
        return st.transform_f(NvimIOState, lambda s: NvimIO.from_either(s))

    @staticmethod
    def failed(e: str) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(NvimIO.failed(e))

    @staticmethod
    def error(e: str) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(NvimIO.error(e))

    @staticmethod
    def inspect_maybe(f: Callable[[S], Either[str, A]], err: CallByName) -> 'NvimIOState[S, A]':
        frame = cframe()
        return NvimIOState.inspect_f(lambda s: NvimIO.from_maybe(f(s), err, frame))

    @staticmethod
    def inspect_either(f: Callable[[S], Either[str, A]]) -> 'NvimIOState[S, A]':
        frame = cframe()
        return NvimIOState.inspect_f(lambda s: NvimIO.from_either(f(s), frame))

    @staticmethod
    def call(name: str, *args: Any, **kw: Any) -> 'NvimIOState[S, A]':
        return NS.delay(__.call(name, *args, **kw))


tcs(NvimIO, NvimIOState)  # type: ignore

NS = NvimIOState


class ToNvimIOState(TypeClass):

    @abc.abstractproperty
    def nvim(self) -> NS:
        ...


class IdStateToNvimIOState(ToNvimIOState, tpe=State):

    @tc_prop
    def nvim(self, fa: State[S, A]) -> NS:
        return NvimIOState.from_id(fa)


class EitherStateToNvimIOState(ToNvimIOState, tpe=EitherState):

    @tc_prop
    def nvim(self, fa: EitherState[S, A]) -> NS:
        return NvimIOState.from_either_state(fa)


__all__ = ('NvimIO', 'NvimIOState', 'NS', 'nvim_request', 'typechecked_request', 'data_cons_request')
