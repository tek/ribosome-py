from types import SimpleNamespace
from typing import Callable, TypeVar, Generic, Any

from amino import List, Boolean, Nil, ADT, Maybe, Either
from amino.boolean import false, true
from amino.tc.base import Implicits, ImplicitsMeta
from amino.dat import ADTMeta
from amino.func import CallByName, call_by_name
from amino.tc.monad import Monad

from ribosome.trans.effect import TransEffect
from ribosome.request.args import ParamsSpec

A = TypeVar('A')
O = TypeVar('O')
A = TypeVar('A')
B = TypeVar('B')


class TransMMeta(ADTMeta, ImplicitsMeta):

    def __new__(cls, name: str, bases: List[type], namespace: SimpleNamespace, **kw: Any) -> None:
        return super().__new__(cls, name, bases, namespace, **kw)

    @property
    def unit(self) -> 'Trans':
        return Trans.pure(None)

    @property
    def id(self) -> 'FreeTrans':
        return TransF.cons(lambda a: a)


class Trans(Generic[A], ADT['Trans'], Implicits, implicits=True, auto=True, base=True, metaclass=TransMMeta):

    @staticmethod
    def from_maybe(fa: Maybe[A], error: CallByName) -> 'Trans[A]':
        return fa / Trans.cont | (lambda: Trans.error(error))

    @staticmethod
    def from_either(fa: Either[str, A]) -> 'Trans[A]':
        return fa.cata(Trans.error, Trans.pure)

    @staticmethod
    def pure(a: A) -> 'Trans[A]':
        return TransMPure(a)

    @staticmethod
    def error(error: CallByName) -> 'Trans[A]':
        return TransMError(call_by_name(error))


class TransMBind(Generic[A], Trans[A]):

    def __init__(self, fa: Trans[A], f: Callable[[A], Trans[B]]) -> None:
        super().__init__()
        self.fa = fa
        self.f = f


class TransMPure(Generic[A], Trans[A]):

    def __init__(self, value: A) -> None:
        self.value = value


class TransMError(Generic[A], Trans[A]):

    def __init__(self, error: str) -> None:
        self.error = error


class Monad_TransM(Monad, tpe=Trans):

    def pure(self, a: A) -> Trans[A]:
        return Trans.pure(a)

    def flat_map(self, fa: Trans, f: Callable[[A], Trans[B]]) -> None:
        return TransMBind(fa, f)


class TransF(Generic[A], Trans[A]):

    @staticmethod
    def cons(
            fun: Callable[..., A],
            effects: List[TransEffect]=Nil,
            resources: Boolean=false,
            internal: Boolean=false,
            component: Boolean=true,
    ) -> 'TransF':
        name = fun.__name__
        return TransF(name, fun, (), effects, resources, internal, component, ParamsSpec.from_function(fun))

    create = cons

    def __init__(
            self,
            name: str,
            fun: Callable[..., A],
            args: tuple,
            effects: List[TransEffect],
            resources: Boolean,
            internal: Boolean,
            component: Boolean,
            params_spec: ParamsSpec,
    ) -> None:
        self.name = name
        self.fun = fun
        self.args = args
        self.effects = effects
        self.resources = resources
        self.internal = internal
        self.component = component
        self.params_spec = params_spec

    def __call__(self, *args: Any) -> 'TransF':
        return self.copy(args=args)


__all__ = ('Trans', 'TransF')
