import abc
import inspect
import traceback
import typing
from typing import TypeVar, Callable, Any, Generic, Generator, Union, Tuple
from threading import Thread

from amino.tc.base import ImplicitInstances, F, TypeClass, tc_prop
from amino.lazy import lazy
from amino.tc.monad import Monad
from amino import Either, __, IO, Maybe, Left, Eval, L, List, Nothing, Right, Lists, _, Just, options
from amino.state import tcs, StateT, State
from amino.func import CallByName, tailrec
from amino.do import do
from amino.io import safe_fmt
from amino.util.string import ToStr
from amino.util.fun import lambda_str
from amino.util.exception import sanitize_tb, format_exception
from amino.dat import ADT

from ribosome.nvim.components import NvimFacade

A = TypeVar('A')
B = TypeVar('B')
S = TypeVar('S')


class NvimIOException(Exception):
    remove_pkgs = List('amino', 'fn')

    def __init__(self, f, stack, cause) -> None:
        self.f = f
        self.stack = List.wrap(stack)
        self.cause = cause

    @property
    def location(self):
        files = List('io', 'anon', 'instances/io', 'tc/base', 'nvim/io')
        def filt(entry, name):
            return entry.filename.endswith('/{}.py'.format(name))
        stack = self.stack.filter_not(lambda a: files.exists(L(filt)(a, _)))
        pred = (lambda a: not NvimIOException.remove_pkgs
                .exists(lambda b: '/{}/'.format(b) in a.filename))
        return stack.find(pred)

    @property
    def format_stack(self) -> List[str]:
        rev = self.stack.reversed
        def remove_recursion(i):
            pre = rev[:i + 1]
            post = rev[i:].drop_while(__.filename.endswith('/amino/io.py'))
            return pre + post
        def remove_internal():
            start = rev.index_where(_.function == 'unsafe_perform_sync')
            return start / remove_recursion | rev
        frames = (self.location.to_list if IO.stack_only_location else remove_internal())
        data = frames / (lambda a: a[1:-2] + tuple(a[-2]))
        return sanitize_tb(Lists.wrap(traceback.format_list(list(data))))

    @property
    def lines(self) -> List[str]:
        cause = format_exception(self.cause)
        suf1 = '' if self.stack.empty else ' at:'
        tb1 = (List() if self.stack.empty else self.format_stack)
        return tb1.cons(f'IO exception{suf1}').cat('Cause:') + cause + List(
            '',
            'Callback:',
            f'  {self.f}'
        )

    def __str__(self):
        return self.lines.join_lines


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


class NvimIO(Generic[A], F[A], ToStr, implicits=True, imp_mod='ribosome.nvim.io', imp_cls='NvimIOInstances'):
    debug = options.io_debug.exists

    @staticmethod
    def wrap_either(f: Callable[[NvimFacade], Either[B, A]]) -> 'NvimIO[A]':
        return NvimIO.suspend(lambda a: f(a).cata(NvimIO.error, NvimIO.pure))

    @staticmethod
    def from_either(e: Either[str, A]) -> 'NvimIO[A]':
        return NvimIO.wrap_either(lambda v: e)

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
        return Suspend(g, safe_fmt(f, ('vim',) + a, kw))

    @staticmethod
    def simple(f: Callable[..., A], *a, **kw) -> 'NvimIO[A]':
        return NvimIO.delay(lambda v: f(*a, **kw))

    @staticmethod
    def suspend(f: Callable[..., 'NvimIO[A]'], *a: Any, **kw: Any) -> 'NvimIO[A]':
        def g(vim: NvimFacade) -> NvimIO[A]:
            return f(vim, *a, **kw)
        return Suspend(g, safe_fmt(f, a, kw))

    @staticmethod
    def pure(a: A) -> 'NvimIO[A]':
        return Pure(a)

    @abc.abstractmethod
    def lambda_str(self) -> Eval[str]:
        ...

    @abc.abstractmethod
    def _flat_map(self, f: Callable[[A], 'NvimIO[B]'], ts: Eval[str], fs: Eval[str]) -> 'NvimIO[B]':
        ...

    @abc.abstractmethod
    def step1(self, vim: NvimFacade) -> 'NvimIO[A]':
        ...

    def __init__(self) -> None:
        self.stack = inspect.stack() if NvimIO.debug else []

    def flat_map(self, f: Callable[[A], 'NvimIO[B]'], ts: Maybe[Eval[str]]=Nothing, fs: Maybe[Eval[str]]=Nothing
                 ) -> 'NvimIO[B]':
        ts1 = ts | self.lambda_str
        fs1 = fs | Eval.later(lambda: f'flat_map({lambda_str(f)})')
        return self._flat_map(f, ts1, fs1)

    def _arg_desc(self) -> List[str]:
        return List(self.lambda_str().evaluate())

    def step(self, vim: NvimFacade) -> Union[A, 'NvimIO[A]']:
        try:
            return self.step1(vim)
        except NvimIOException as e:
            raise e
        except Exception as e:
            raise NvimIOException(self.lambda_str().evaluate(), self.stack, e)

    def run(self, vim: NvimFacade) -> A:
        @tailrec
        def run(t: Union[A, 'NvimIO[A]']) -> Union[Tuple[bool, A], Tuple[bool, Tuple[Union[A, 'NvimIO[A]']]]]:
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

    def with_stack(self, s: typing.List[inspect.FrameInfo]) -> 'IO[A]':
        self.stack = s
        return self

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


class Suspend(Generic[A], NvimIO[A]):

    def __init__(self, thunk: Callable[[NvimFacade], NvimIO[A]], string: Eval[str]) -> None:
        super().__init__()
        self.thunk = thunk
        self.string = string

    def lambda_str(self) -> Eval[str]:
        return self.string

    def step1(self, vim: NvimFacade) -> NvimIO[A]:
        return self.thunk(vim).with_stack(self.stack)

    def _flat_map(self, f: Callable[[A], NvimIO[B]], ts: Eval[str], fs: Eval[str]) -> NvimIO[B]:
        return BindSuspend(self.thunk, f, ts, fs)


class BindSuspend(Generic[A], NvimIO[A]):

    def __init__(self, thunk: Callable[[NvimFacade], NvimIO[A]], f: Callable, ts: Eval[str], fs: Eval[str]) -> None:
        super().__init__()
        self.thunk = thunk
        self.f = f
        self.ts = ts
        self.fs = fs

    def lambda_str(self) -> Eval[str]:
        return (self.ts & self.fs).map2('{}.{}'.format)

    def step1(self, vim: NvimFacade) -> NvimIO[A]:
        return (
            self.thunk(vim)
            .flat_map(self.f, fs=Just(self.fs))
            .with_stack(self.stack)
        )

    def _flat_map(self, f: Callable[[A], NvimIO[B]], ts: Eval[str], fs: Eval[str]) -> NvimIO[B]:
        def bs(vim: NvimFacade) -> NvimIO[B]:
            return BindSuspend(self.thunk, lambda a: self.f(a).flat_map(f, Just(ts), Just(fs)), ts, fs)
        return Suspend(bs, (ts & fs).map2('{}.{}'.format))


class Pure(Generic[A], NvimIO[A]):

    def __init__(self, value: A) -> None:
        super().__init__()
        self.value = value

    def lambda_str(self) -> Eval[str]:
        return Eval.later(lambda: f'Pure({self.value})')

    def _arg_desc(self) -> List[str]:
        return List(str(self.value))

    def step1(self, vim: NvimFacade) -> NvimIO[A]:
        return self

    def _flat_map(self, f: Callable[[A], NvimIO[B]], ts: Eval[str], fs: Eval[str]) -> NvimIO[B]:
        def g(vim: NvimFacade) -> NvimIO[B]:
            return f(self.value)
        return Suspend(g, (ts & fs).map2('{}.{}'.format))


class NvimIOError(Generic[A], NvimIO[A]):

    def __init__(self, error: str) -> None:
        self.error = error

    def _arg_desc(self) -> List[str]:
        return List(str(self.error))

    def lambda_str(self) -> Eval[str]:
        return Eval.later(lambda: f'NvimIOError({self.error})')

    def _flat_map(self, f: Callable[[A], NvimIO[B]], ts: Eval[str], fs: Eval[str]) -> NvimIO[B]:
        return self

    def step1(self, vim: NvimFacade) -> NvimIO[A]:
        return self


class NvimIOFatal(Generic[A], NvimIO[A]):

    def __init__(self, exception: Exception) -> None:
        self.exception = exception

    def _arg_desc(self) -> List[str]:
        return List(str(self.exception))

    def lambda_str(self) -> Eval[str]:
        return Eval.later(lambda: f'NvimIOFatal({self.exception})')

    def _flat_map(self, f: Callable[[A], NvimIO[B]], ts: Eval[str], fs: Eval[str]) -> NvimIO[B]:
        return self

    def step1(self, vim: NvimFacade) -> NvimIO[A]:
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
    def failed(e: str) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(NvimIO.failed(e))

    @staticmethod
    def error(e: str) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(NvimIO.error(e))

    @staticmethod
    def inspect_either(f: Callable[[S], Either[str, A]]) -> 'NvimIOState[S, A]':
        return NvimIOState.inspect_f(lambda s: NvimIO.from_either(f(s)))

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

__all__ = ('NvimIO', 'NvimIOState', 'NS')
