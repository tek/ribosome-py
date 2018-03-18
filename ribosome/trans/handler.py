import abc
from typing import Callable, TypeVar, Type, Generic, Any

from amino import List, Boolean, Nil, ADT
from amino.boolean import false, true
from amino.tc.base import Implicits, ImplicitsMeta
from amino.dat import ADTMeta

from ribosome.trans.effect import TransEffect
from ribosome.trans.message_base import Message, default_prio
from ribosome.request.args import ParamsSpec

M = TypeVar('M', bound=Message)
A = TypeVar('A')
O = TypeVar('O')
A = TypeVar('A')
B = TypeVar('B')


class TransHandlerMeta(ADTMeta, ImplicitsMeta):

    @property
    def id(self) -> 'FreeTrans':
        return FreeTrans.cons(lambda a: a)


class TransHandler(Generic[A], ADT['TransHandler[A]'], Implicits, auto=True, implicits=True, metaclass=TransHandlerMeta
                   ):

    @abc.abstractmethod
    def __call__(self, *args: Any) -> 'TransHandler[A]':
        ...


class MessageTrans(Generic[A, M], TransHandler[A]):

    @staticmethod
    def create(fun: Callable[[M], A], msg: Type[M], effects: List[TransEffect], prio: float) -> 'TransHandler[A]':
        name = fun.__name__
        return MessageTrans(name, fun, msg, effects, prio)

    def __init__(self, name: str, fun: Callable[[M], A], message: Type[M], effects: List[TransEffect], prio: float
                 ) -> None:
        self.name = name
        self.message = message
        self.fun = fun
        self.prio = prio
        self.effects = effects

    def __call__(self, *args: Any) -> TransHandler[A]:
        return self

    @property
    def params_spec(self) -> ParamsSpec:
        return ParamsSpec.from_type(self.message)


class FreeTrans(Generic[A], TransHandler[A]):

    @staticmethod
    def cons(
            fun: Callable[..., A],
            effects: List[TransEffect]=Nil,
            prio: float=default_prio,
            resources: Boolean=false,
            internal: Boolean=false,
            component: Boolean=true,
    ) -> 'FreeTrans':
        name = fun.__name__
        return FreeTrans(name, fun, (), effects, prio, resources, internal, component, ParamsSpec.from_function(fun))

    create = cons

    def __init__(
            self,
            name: str,
            fun: Callable[..., A],
            args: tuple,
            effects: List[TransEffect],
            prio: float,
            resources: Boolean,
            internal: Boolean,
            component: Boolean,
            params_spec: ParamsSpec,
    ) -> None:
        self.name = name
        self.fun = fun
        self.args = args
        self.effects = effects
        self.prio = prio
        self.resources = resources
        self.internal = internal
        self.component = component
        self.params_spec = params_spec

    def __call__(self, *args: Any) -> 'FreeTrans':
        return self.copy(args=args)


__all__ = ('MessageTrans', 'FreeTrans')
