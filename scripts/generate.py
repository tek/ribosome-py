#!usr/bin/env python3

from amino.meta.gen_state import state_task
from amino import Path, List
from amino.meta.gen import codegen_write

meta_extra = '''\
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
'''

extra = '''
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
'''

extra_import = List(
    'import abc',
    'from amino.tc.base import TypeClass, tc_prop',
    'from amino.state import State, EitherState',
    'from ribosome.nvim.api.data import NvimApi',
    'from ribosome.nvim.io.api import N',
    'from amino import IO, Maybe, Either',
    'from amino.func import CallByName',
    '''E = TypeVar('E')''',
)
pkg = Path(__file__).absolute().parent.parent
task = state_task('NvimIO', 'ribosome.nvim.io.compute', meta_extra=meta_extra, ctor_extra=meta_extra,
                  extra_import=extra_import, extra=extra)
outpath = pkg / 'ribosome' / 'nvim' / 'io' / f'state.py'

codegen_write(task, outpath).fatal
