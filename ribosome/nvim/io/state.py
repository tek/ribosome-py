from typing import Generic, TypeVar, Callable, Tuple, cast, Type, Any

from lenses import UnboundLens

from amino.tc.base import ImplicitsMeta, Implicits
from amino.tc.monad import Monad
from amino.tc.zip import Zip
from amino.instances.list import ListTraverse
from amino import List, curried
from amino.util.string import ToStr
from amino.state.base import StateT
from ribosome.nvim.io.compute import NvimIO

import abc
from amino.tc.base import TypeClass, tc_prop
from amino.state import State, EitherState
from ribosome.nvim.api.data import NvimApi
from ribosome.nvim.io.api import N
from amino import IO, Maybe, Either
from amino.func import CallByName
E = TypeVar('E')

A = TypeVar('A')
B = TypeVar('B')
S = TypeVar('S')
R = TypeVar('R')
ST1 = TypeVar('ST1')


monad: Monad = cast(Monad, Monad.fatal(NvimIO))


class NvimIOStateCtor(Generic[S]):

    def inspect(self, f: Callable[[S], A]) -> 'NvimIOState[S, A]':
        def g(s: S) -> NvimIO[Tuple[S, A]]:
            return monad.pure((s, f(s)))
        return NvimIOState.apply(g)

    def inspect_f(self, f: Callable[[S], NvimIO[A]]) -> 'NvimIOState[S, A]':
        def g(s: S) -> NvimIO[Tuple[S, A]]:
            return f(s).map(lambda a: (s, a))
        return NvimIOState.apply(g)

    def pure(self, a: A) -> 'NvimIOState[S, A]':
        return NvimIOState.apply(lambda s: monad.pure((s, a)))

    def delay(self, fa: Callable[..., A], *a: Any, **kw: Any) -> 'NvimIOState[S, A]':
        return NvimIOState.apply(lambda s: monad.pure((s, fa(*a, **kw))))

    def lift(self, fa: NvimIO[A]) -> 'NvimIOState[S, A]':
        def g(s: S) -> NvimIO[Tuple[S, A]]:
            return fa.map(lambda a: (s, a))
        return NvimIOState.apply(g)

    def modify(self, f: Callable[[S], S]) -> 'NvimIOState[S, None]':
        return NvimIOState.apply(lambda s: monad.pure((f(s), None)))

    def modify_f(self, f: Callable[[S], NvimIO[S]]) -> 'NvimIOState[S, None]':
        return NvimIOState.apply(lambda s: f(s).map(lambda a: (a, None)))

    def get(self) -> 'NvimIOState[S, S]':
        return self.inspect(lambda a: a)

    @property
    def unit(self) -> 'NvimIOState[S, None]':
        return NvimIOState.pure(None)

    def io(self, f: Callable[[NvimApi], A]) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(N.delay(f))

    def delay(self, f: Callable[[NvimApi], A]) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(N.delay(f))

    def suspend(self, f: Callable[[NvimApi], NvimIO[A]]) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(N.suspend(f))

    def from_io(self, io: IO[A]) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(N.wrap_either(lambda v: io.attempt))

    def from_id(self, st: State[S, A]) -> 'NvimIOState[S, A]':
        return st.transform_f(NvimIOState, lambda s: N.pure(s.value))

    def from_maybe(self, a: Maybe[B], err: CallByName) -> 'NvimIOState[S, B]':
        return NvimIOState.lift(N.from_maybe(a, err))

    m = from_maybe

    def from_either(self, e: Either[str, A]) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(N.from_either(e))

    e = from_either

    def from_either_state(self, st: EitherState[E, S, A]) -> 'NvimIOState[S, A]':
        return st.transform_f(NvimIOState, lambda s: N.from_either(s))

    def failed(self, e: str) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(N.failed(e))

    def error(self, e: str) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(N.error(e))

    def inspect_maybe(self, f: Callable[[S], Maybe[A]], err: CallByName) -> 'NvimIOState[S, A]':
        return NvimIOState.inspect_f(lambda s: N.from_maybe(f(s), err))

    def inspect_either(self, f: Callable[[S], Either[str, A]]) -> 'NvimIOState[S, A]':
        return NvimIOState.inspect_f(lambda s: N.from_either(f(s)))

    def simple(self, f: Callable[..., A], *a: Any, **kw: Any) -> 'NvimIOState[S, A]':
        return NS.lift(N.simple(f, *a, **kw))

    def sleep(self, duration: float) -> 'NvimIOState[S, None]':
        return NS.lift(N.sleep(duration))


class NvimIOStateMeta(ImplicitsMeta):

    def cons(self, run_f: NvimIO[Callable[[S], NvimIO[Tuple[S, A]]]]) -> 'NvimIOState[S, A]':
        return self(run_f)

    def apply(self, f: Callable[[S], NvimIO[Tuple[S, A]]]) -> 'NvimIOState[S, A]':
        return self.cons(monad.pure(f))

    def apply_f(self, run_f: NvimIO[Callable[[S], NvimIO[Tuple[S, A]]]]) -> 'NvimIOState[S, A]':
        return self.cons(run_f)

    def inspect(self, f: Callable[[S], A]) -> 'NvimIOState[S, A]':
        def g(s: S) -> NvimIO[Tuple[S, A]]:
            return monad.pure((s, f(s)))
        return self.apply(g)

    def inspect_f(self, f: Callable[[S], NvimIO[A]]) -> 'NvimIOState[S, A]':
        def g(s: S) -> NvimIO[Tuple[S, A]]:
            return f(s).map(lambda a: (s, a))
        return self.apply(g)

    def pure(self, a: A) -> 'NvimIOState[S, A]':
        return self.apply(lambda s: monad.pure((s, a)))

    def reset(self, s: S, a: A) -> 'NvimIOState[S, A]':
        return self.apply(lambda _: monad.pure((s, a)))

    def reset_t(self, t: Tuple[S, A]) -> 'NvimIOState[S, A]':
        return self.apply(lambda _: monad.pure(t))

    def delay(self, fa: Callable[..., A], *a: Any, **kw: Any) -> 'NvimIOState[S, A]':
        return self.apply(lambda s: monad.pure((s, fa(*a, **kw))))

    def lift(self, fa: NvimIO[A]) -> 'NvimIOState[S, A]':
        def g(s: S) -> NvimIO[Tuple[S, A]]:
            return fa.map(lambda a: (s, a))
        return self.apply(g)

    def modify(self, f: Callable[[S], S]) -> 'NvimIOState[S, None]':
        return self.apply(lambda s: monad.pure((f(s), None)))

    def modify_f(self, f: Callable[[S], NvimIO[S]]) -> 'NvimIOState[S, None]':
        return self.apply(lambda s: f(s).map(lambda a: (a, None)))

    def set(self, s: S) -> 'NvimIOState[S, None]':
        return self.modify(lambda s0: s)

    def get(self) -> 'NvimIOState[S, S]':
        return self.inspect(lambda a: a)

    @property
    def unit(self) -> 'NvimIOState[S, None]':
        return NvimIOState.pure(None)

    def s(self, tpe: Type[S]) -> NvimIOStateCtor[S]:
        return NvimIOStateCtor()

    def io(self, f: Callable[[NvimApi], A]) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(N.delay(f))

    def delay(self, f: Callable[[NvimApi], A]) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(N.delay(f))

    def suspend(self, f: Callable[[NvimApi], NvimIO[A]]) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(N.suspend(f))

    def from_io(self, io: IO[A]) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(N.wrap_either(lambda v: io.attempt))

    def from_id(self, st: State[S, A]) -> 'NvimIOState[S, A]':
        return st.transform_f(NvimIOState, lambda s: N.pure(s.value))

    def from_maybe(self, a: Maybe[B], err: CallByName) -> 'NvimIOState[S, B]':
        return NvimIOState.lift(N.from_maybe(a, err))

    m = from_maybe

    def from_either(self, e: Either[str, A]) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(N.from_either(e))

    e = from_either

    def from_either_state(self, st: EitherState[E, S, A]) -> 'NvimIOState[S, A]':
        return st.transform_f(NvimIOState, lambda s: N.from_either(s))

    def failed(self, e: str) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(N.failed(e))

    def error(self, e: str) -> 'NvimIOState[S, A]':
        return NvimIOState.lift(N.error(e))

    def inspect_maybe(self, f: Callable[[S], Maybe[A]], err: CallByName) -> 'NvimIOState[S, A]':
        return NvimIOState.inspect_f(lambda s: N.from_maybe(f(s), err))

    def inspect_either(self, f: Callable[[S], Either[str, A]]) -> 'NvimIOState[S, A]':
        return NvimIOState.inspect_f(lambda s: N.from_either(f(s)))

    def simple(self, f: Callable[..., A], *a: Any, **kw: Any) -> 'NvimIOState[S, A]':
        return NS.lift(N.simple(f, *a, **kw))

    def sleep(self, duration: float) -> 'NvimIOState[S, None]':
        return NS.lift(N.sleep(duration))


class NvimIOState(Generic[S, A], StateT, ToStr, Implicits, implicits=True, auto=True, metaclass=NvimIOStateMeta):

    def __init__(self, run_f: NvimIO[Callable[[S], NvimIO[Tuple[S, A]]]]) -> None:
        self.run_f = run_f

    @property
    def cls(self) -> Type['NvimIOState[S, A]']:
        return type(self)

    def run(self, s: S) -> NvimIO[Tuple[S, A]]:
        return self.run_f.flat_map(lambda f: f(s))

    def run_s(self, s: S) -> NvimIO[S]:
        return self.run(s).map(lambda a: a[0])

    def run_a(self, s: S) -> NvimIO[S]:
        return self.run(s).map(lambda a: a[1])

    def _arg_desc(self) -> List[str]:
        return List(str(self.run_f))

    def flat_map_f(self, f: Callable[[A], NvimIO[B]]) -> 'NvimIOState[S, B]':
        def h(s: S, a: A) -> NvimIO[Tuple[S, B]]:
            return f(a).map(lambda b: (s, b))
        def g(fsa: NvimIO[Tuple[S, A]]) -> NvimIO[Tuple[S, B]]:
            return fsa.flat_map2(h)
        run_f1 = self.run_f.map(lambda sfsa: lambda a: g(sfsa(a)))
        return self.cls.apply_f(run_f1)

    def transform(self, f: Callable[[Tuple[S, A]], Tuple[S, B]]) -> 'NvimIOState[S, B]':
        def g(fsa: NvimIO[Tuple[S, A]]) -> NvimIO[Tuple[S, B]]:
            return fsa.map2(f)
        run_f1 = self.run_f.map(lambda sfsa: lambda a: g(sfsa(a)))
        return self.cls.apply_f(run_f1)

    def transform_s(self, f: Callable[[R], S], g: Callable[[R, S], R]) -> 'NvimIOState[R, A]':
        def trans(sfsa: Callable[[S], NvimIO[Tuple[S, A]]], r: R) -> NvimIO[Tuple[R, A]]:
            s = f(r)
            return sfsa(s).map2(lambda s, a: (g(r, s), a))
        return self.cls.apply_f(self.run_f.map(curried(trans)))

    def transform_f(self, tpe: Type[ST1], f: Callable[[NvimIO[Tuple[S, A]]], Any]) -> ST1:
        def trans(s: S) -> Any:
            return f(self.run(s))
        return tpe.apply(trans)  # type: ignore

    def zoom(self, l: UnboundLens) -> 'NvimIOState[R, A]':
        return self.transform_s(l.get(), lambda r, s: l.set(s)(r))

    transform_s_lens = zoom

    def read_zoom(self, l: UnboundLens) -> 'NvimIOState[R, A]':
        return self.transform_s(l.get(), lambda r, s: r)

    transform_s_lens_read = read_zoom

    def flat_map(self, f: Callable[[A], 'NvimIOState[S, B]']) -> 'NvimIOState[S, B]':
        return Monad_NvimIOState.flat_map(self, f)


def run_function(s: NvimIOState[S, A]) -> NvimIO[Callable[[S], NvimIO[Tuple[S, A]]]]:
    try:
        return s.run_f
    except Exception as e:
        if not isinstance(s, NvimIOState):
            raise TypeError(f'flatMapped {s} into NvimIOState')
        else:
            raise


class NvimIOStateMonad(Monad, tpe=NvimIOState):

    def pure(self, a: A) -> NvimIOState[S, A]:  # type: ignore
        return NvimIOState.pure(a)

    def flat_map(  # type: ignore
            self,
            fa: NvimIOState[S, A],
            f: Callable[[A], NvimIOState[S, B]]
    ) -> NvimIOState[S, B]:
        def h(s: S, a: A) -> NvimIO[Tuple[S, B]]:
            return f(a).run(s)
        def g(fsa: NvimIO[Tuple[S, A]]) -> NvimIO[Tuple[S, B]]:
            return fsa.flat_map2(h)
        def i(sfsa: Callable[[S], NvimIO[Tuple[S, A]]]) -> Callable[[S], NvimIO[Tuple[S, B]]]:
            return lambda a: g(sfsa(a))
        run_f1 = run_function(fa).map(i)
        return NvimIOState.apply_f(run_f1)


Monad_NvimIOState = NvimIOStateMonad()


class NvimIOStateZip(Zip, tpe=NvimIOState):

    def zip(
            self,
            fa: NvimIOState[S, A],
            fb: NvimIOState[S, A],
            *fs: NvimIOState[S, A],
    ) -> NvimIOState[S, List[A]]:
        v = ListTraverse().sequence(List(fa, fb, *fs), NvimIOState)  # type: ignore
        return cast(NvimIOState[S, List[A]], v)


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
    def nvim(self, fa: EitherState[E, S, A]) -> NS:
        return NvimIOState.from_either_state(fa)


__all__ = ('NvimIOState',)
