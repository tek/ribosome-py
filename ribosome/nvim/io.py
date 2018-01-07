import abc
import inspect
from traceback import FrameSummary
from typing import TypeVar, Callable, Any, Generic, Generator, Union, Tuple
from threading import Thread

from amino.tc.base import ImplicitInstances, F, TypeClass, tc_prop
from amino.lazy import lazy
from amino.tc.monad import Monad
from amino import Either, __, IO, Maybe, Left, Eval, L, List, Right, Lists, _, options, Nil, Try, Path
from amino.state import tcs, StateT, State, EitherState
from amino.func import CallByName, tailrec
from amino.do import do
from amino.util.exception import format_exception
from amino.dat import ADT

from ribosome.nvim.components import NvimFacade

A = TypeVar('A')
B = TypeVar('B')
C = TypeVar('C')
S = TypeVar('S')


def cframe() -> FrameSummary:
    return inspect.currentframe()


def callsite(frame) -> Any:
    def loop(f) -> None:
        pkg = f.f_globals.get('__package__')
        return loop(f.f_back) if pkg.startswith('ribosome.nvim') or pkg.startswith('amino') else f
    return loop(frame)


def callsite_info(frame: FrameSummary) -> List[str]:
    cs = callsite(frame)
    source = inspect.getsourcefile(cs.f_code)
    line = cs.f_lineno
    code = Try(Path, source) // (lambda a: Try(a.read_text)) / Lists.lines // __.lift(line - 1) | '<no source>'
    fun = cs.f_code.co_name
    clean = code.strip()
    return List(f'  File "{source}", line {line}, in {fun}', f'    {clean}')


def callsite_source(frame) -> Tuple[List[str], int]:
    cs = callsite(frame)
    source = inspect.getsourcefile(cs.f_code)
    return Try(Path, source) // (lambda a: Try(a.read_text)) / Lists.lines // __.lift(cs.f_lineno - 1) | '<no source>'


class NvimIOException(Exception):

    def __init__(self, f, stack, cause, frame=None) -> None:
        self.f = f
        self.stack = List.wrap(stack)
        self.cause = cause
        self.frame = frame

    @property
    def lines(self) -> List[str]:
        cause = format_exception(self.cause)
        cs = callsite_info(self.frame)
        return List(f'NvimIO exception') + cs + cause[-3:]

    def __str__(self):
        return self.lines.join_lines

    @property
    def callsite(self) -> Any:
        return callsite(self.frame)

    @property
    def callsite_source(self) -> List[str]:
        return callsite_source(self.frame)


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


class NvimIO(Generic[A], F[A], ADT['NvimIO'], implicits=True, imp_mod='ribosome.nvim.io', imp_cls='NvimIOInstances'):
    debug = options.io_debug.exists

    @staticmethod
    def wrap_either(f: Callable[[NvimFacade], Either[B, A]], frame: FrameSummary=None) -> 'NvimIO[A]':
        return NvimIO.suspend(lambda a: f(a).cata(NvimIO.error, NvimIO.pure), _frame=frame)

    @staticmethod
    def from_either(e: Either[str, A], frame: FrameSummary=None) -> 'NvimIO[A]':
        return NvimIO.wrap_either(lambda v: e, frame)

    @staticmethod
    def from_maybe(e: Maybe[A], error: CallByName) -> 'NvimIO[A]':
        return NvimIO.from_either(e.to_either(error))

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
        return NvimIO.delay(self.attempt).map(__.value_or(f))

    # FIXME use NResult
    @do('NvimIO[A]')
    def ensure(self, f: Callable[[Either[Exception, A]], 'NvimIO[None]']) -> Generator:
        result = yield NvimIO.delay(self.attempt)
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
    def inspect_either(f: Callable[[S], Either[str, A]]) -> 'NvimIOState[S, A]':
        frame = cframe()
        return NvimIOState.inspect_f(lambda s: NvimIO.from_either(f(s), frame))

    @staticmethod
    def call(name: str, *args: Any, **kw: Any) -> 'NvimIOState[S, A]':
        return NS.delay(__.call(name, *args, **kw))


tcs(NvimIO, NvimIOState)  # type: ignore

NS = NvimIOState


class ToNvimStateIO(TypeClass):

    @abc.abstractproperty
    def nvim(self) -> NS:
        ...


class IdStateToNvimStateIO(ToNvimStateIO, tpe=State):

    @tc_prop
    def nvim(self, fa: State[S, A]) -> NS:
        return NvimIOState.from_id(fa)


class EitherStateToNvimStateIO(ToNvimStateIO, tpe=EitherState):

    @tc_prop
    def nvim(self, fa: EitherState[S, A]) -> NS:
        return NvimIOState.from_either_state(fa)


__all__ = ('NvimIO', 'NvimIOState', 'NS')
