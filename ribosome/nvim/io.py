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
from amino import Either, __, IO, Maybe, Left, Eval, List, Right, options, Nil, Do, Just, Try, Lists
from amino.state import tcs, StateT, State, EitherState
from amino.func import CallByName, tailrec
from amino.do import do
from amino.dat import ADT, ADTMeta
from amino.io import IOExceptionBase
from amino.util.trace import default_internal_packages, cframe, callsite_source

from ribosome.nvim.components import NvimFacade

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
    def wrap_either(f: Callable[[NvimFacade], Either[B, A]], frame: FrameSummary=None) -> 'NvimIO[A]':
        return NvimIO.suspend(lambda a: f(a).cata(NvimIO.error, NvimIO.pure), _frame=frame)

    @staticmethod
    def from_either(e: Either[str, A], frame: FrameSummary=None) -> 'NvimIO[A]':
        return NvimIO.wrap_either(lambda v: e, frame)

    @staticmethod
    def from_maybe(e: Maybe[A], error: CallByName, frame: FrameSummary=None) -> 'NvimIO[A]':
        return NvimIO.from_either(e.to_either(error), frame)

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

    @staticmethod
    def fork(f: Callable[[NvimFacade], None]) -> 'NvimIO[None]':
        return NvimIO.delay(lambda v: Thread(target=f, args=(v,)).start())

    @staticmethod
    def delay(f: Callable[..., A], *a: Any, **kw: Any) -> 'NvimIO[A]':
        def g(vim: NvimFacade) -> A:
            return Pure(f(vim, *a, **kw))
        return Suspend(g)

    @staticmethod
    def simple(f: Callable[..., A], *a, **kw) -> 'NvimIO[A]':
        return NvimIO.delay(lambda v: f(*a, **kw))

    @staticmethod
    def suspend(f: Callable[..., 'NvimIO[A]'], *a: Any, _frame: FrameSummary=None, **kw: Any) -> 'NvimIO[A]':
        def g(vim: NvimFacade) -> NvimIO[A]:
            return f(vim, *a, **kw)
        return Suspend(g, _frame)

    @staticmethod
    def pure(a: A) -> 'NvimIO[A]':
        return Pure(a)

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
        return request(cmd, *args).replace(None)

    @abc.abstractmethod
    def _flat_map(self, f: Callable[[A], 'NvimIO[B]'], ts: Eval[str], fs: Eval[str]) -> 'NvimIO[B]':
        ...

    @abc.abstractmethod
    def step(self, vim: NvimFacade) -> 'NvimIO[A]':
        ...

    def __init__(self, frame=None) -> None:
        self.frame = frame or inspect.currentframe()

    def flat_map(self, f: Callable[[A], 'NvimIO[B]']) -> 'NvimIO[B]':
        return self._flat_map(f)

    def run(self, vim: NvimFacade) -> A:
        @tailrec
        def run(t: 'NvimIO[A]') -> Union[Tuple[bool, A], Tuple[bool, Tuple[Union[A, 'NvimIO[A]']]]]:
            if isinstance(t, Pure):
                return True, (t.value,)
            elif isinstance(t, (Suspend, BindSuspend)):
                return True, (t.step(vim),)
            elif isinstance(t, NvimIOError):
                return False, NError(t.error)
            elif isinstance(t, NvimIOFatal):
                return False, NFatal(t.exception)
            else:
                return False, NSuccess(t)
        return run(self)

    def result(self, vim: NvimFacade) -> NResult[A]:
        try:
            return self.run(vim)
        except NvimIOException as e:
            return NFatal(e)

    def either(self, vim: NvimFacade) -> Either[NvimIOException, A]:
        try:
            return self.run(vim).to_either
        except NvimIOException as e:
            return Left(e)

    def attempt(self, vim: NvimFacade) -> Either[NvimIOException, A]:
        return self.either(vim)

    def unsafe(self, vim: NvimFacade) -> A:
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
        def wrap(v: NvimFacade) -> A:
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


class Suspend(Generic[A], NvimIO[A]):

    def __init__(self, thunk: Callable[[NvimFacade], NvimIO[A]], frame: FrameSummary=None) -> None:
        super().__init__(frame)
        self.thunk = thunk

    def step(self, vim: NvimFacade) -> NvimIO[A]:
        try:
            return self.thunk(vim)
        except NvimIOException as e:
            raise e
        except Exception as e:
            raise NvimIOException('', Nil, e, self.frame)

    def _flat_map(self, f: Callable[[A], NvimIO[B]]) -> NvimIO[B]:
        return BindSuspend(self.thunk, f, self.frame)


class BindSuspend(Generic[A, B], NvimIO[B]):

    def __init__(self, thunk: Callable[[NvimFacade], NvimIO[A]], f: Callable[[A], NvimIO[B]], frame: FrameSummary
                 ) -> None:
        super().__init__(frame)
        self.thunk = thunk
        self.f = f

    def step(self, vim: NvimFacade) -> NvimIO[B]:
        try:
            step = self.thunk(vim)
        except NvimIOException as e:
            raise e
        except Exception as e:
            raise NvimIOException('', Nil, e, self.frame)
        try:
            return step.flat_map(self.f)
        except NvimIOException as e:
            raise e
        except Exception as e:
            raise NvimIOException('', Nil, e, step.frame)

    def _flat_map(self, f: Callable[[B], NvimIO[C]]) -> NvimIO[C]:
        def bs(vim: NvimFacade) -> NvimIO[C]:
            return BindSuspend(self.thunk, lambda a: self.f(a).flat_map(f), self.frame)
        return Suspend(bs)


class Pure(Generic[A], NvimIO[A]):

    def __init__(self, value: A) -> None:
        super().__init__()
        self.value = value

    def _arg_desc(self) -> List[str]:
        return List(str(self.value))

    def step(self, vim: NvimFacade) -> NvimIO[A]:
        return self

    def _flat_map(self, f: Callable[[A], NvimIO[B]]) -> NvimIO[B]:
        def g(vim: NvimFacade) -> NvimIO[B]:
            return f(self.value)
        return Suspend(g)


class NvimIOError(Generic[A], NvimIO[A]):

    def __init__(self, error: str) -> None:
        self.error = error

    def _flat_map(self, f: Callable[[A], NvimIO[B]]) -> NvimIO[B]:
        return self

    def step(self, vim: NvimFacade) -> NvimIO[A]:
        return self


class NvimIOFatal(Generic[A], NvimIO[A]):

    def __init__(self, exception: Exception) -> None:
        self.exception = exception

    def _flat_map(self, f: Callable[[A], NvimIO[B]]) -> NvimIO[B]:
        return self

    def step(self, vim: NvimFacade) -> NvimIO[A]:
        return self


class NvimIOMonad(Monad[NvimIO]):

    def pure(self, a: A) -> NvimIO[A]:
        return NvimIO.pure(a)

    def flat_map(self, fa: NvimIO[A], f: Callable[[A], NvimIO[B]]) -> NvimIO[B]:
        return fa.flat_map(f)


def nvim_error_msg(exc: NvimError) -> str:
    return Try(lambda: exc.args[0].decode()) | str(exc)


def nvim_request(name: str, *args: Any) -> NvimIO[A]:
    def wrap_error(error: NvimIOException) -> NvimIO[A]:
        msg = nvim_error_msg(error.cause) if isinstance(error.cause, NvimError) else str(error.cause)
        argsl = Lists.wrap(args)
        return NvimIOError(f'error in nvim request `{name}({argsl.join_comma})`: {msg}')
    return NvimIO.delay(__.vim._session.request(name, *args)).recover_with(wrap_error)


request = nvim_request


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
    raw = yield request(name, *args)
    yield NvimIO.from_either(cons(raw))


class NvimIOState(Generic[S, A], StateT[NvimIO, S, A], tpe=NvimIO):

    @staticmethod
    def io(f: Callable[[NvimFacade], A]) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(NvimIO.delay(f))

    @staticmethod
    def delay(f: Callable[[NvimFacade], A]) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(NvimIO.delay(f))

    @staticmethod
    def suspend(f: Callable[[NvimFacade], NvimIO[A]]) -> 'NvimIOState[S, A]':
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
