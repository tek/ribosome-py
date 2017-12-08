import abc
import functools
import time
import inspect
from typing import Optional, Any, TypeVar, Type, Generic
from types import FunctionType, SimpleNamespace

from amino import Map, Just, L, Maybe, _, Lists, Nothing
from amino.dat import Dat, DatMeta
from amino.util.ast import synth_init

_machine_attr = '_machine'
_message_attr = '_message'
_prio_attr = '_prio'
_dyn_attr = '_dyn'
default_prio = 0.5
fallback_prio = 0.3
override_prio = 0.8


class Sendable:

    @abc.abstractproperty
    def msg(self) -> 'Message':
        ...


M = TypeVar('M', bound='Message')


class Message(Generic[M], Dat[M], Sendable):

    def at(self, prio: float) -> 'Envelope[M]':
        return Envelope(self, time.time(), prio, Nothing)

    @property
    def envelope(self) -> 'Envelope[M]':
        return self.at(0.5)

    @property
    def pub(self) -> 'Envelope[M]':
        return self.envelope

    def to(self, target: str) -> 'Envelope[M]':
        return self.envelope.copy(recipient=Just(target))

    @property
    def msg(self) -> 'Message':
        return self


def message_init(fields: Map[str, Type], _globals: dict) -> FunctionType:
    params = fields.to_list
    return synth_init(params, _globals)


class MsgMeta(DatMeta):

    @classmethod
    def __prepare__(cls, _name: str, bases: tuple, glob: dict=None, **kw: Any) -> dict:
        globs = glob or inspect.currentframe().f_back.f_globals
        return dict(__init__=message_init(Map(kw), globs)) if kw else dict()

    def __new__(cls, _name: str, bases: tuple, namespace: SimpleNamespace, **kw: Any) -> type:
        return super().__new__(cls, _name, bases, namespace)


class Msg(Generic[M], Message[M], metaclass=MsgMeta):
    pass


def message_definition_module() -> Optional[str]:
    return inspect.currentframe().f_back.f_back.f_globals['__name__']


def pmessage(_name: str, *fields: str, mod: str=None, **kw: Any) -> Type[M]:
    module = mod or message_definition_module()
    params = Map(Lists.wrap(fields).apzip(lambda a: Any))
    ns = MsgMeta.__prepare__(_name, (Msg,), glob=dict(__module__=module), **params, **kw)
    return MsgMeta(_name, (Msg,), ns, **kw)


def json_pmessage(name, *fields, mod=None, **kw):
    module = mod or message_definition_module()
    return pmessage(name, *fields, mod=module, options=Map, **kw)


@functools.total_ordering
class Envelope(Generic[M], Dat['Envelope[M]'], Sendable):

    @staticmethod
    def from_sendable(s: Sendable) -> 'Envelope[M]':
        return s if isinstance(s, Envelope) else Envelope.default(s)

    @staticmethod
    def default(m: Message[M]) -> 'Envelope[M]':
        return Envelope(m, time.time(), 0.5, Nothing)

    def __init__(self, message: Message[M], time: float, prio: float, recipient: Maybe[str]) -> None:
        self.message = message
        self.time = time
        self.prio = prio
        self.recipient = recipient

    def at(self, prio: float) -> 'Envelope[M]':
        return self.copy(prio=prio)

    def __lt__(self, other):
        return (
            not isinstance(other, Envelope) or
            (
                self.time < self.time
                if self.prio == other.prio else
                self.prio < other.prio
            )
        )

    @property
    def delivery(self) -> Message:
        return self.recipient / L(ToMachine)(self, _) | self.message

    @property
    def msg(self) -> 'Message':
        return self.message


class ToMachine(Generic[M], Dat['ToMachine[M]'], Sendable):

    def __init__(self, envelope: Envelope[M], target: str) -> None:
        self.envelope = envelope
        self.target = target

    @property
    def message(self) -> Message[M]:
        return self.envelope.message

    @property
    def msg(self) -> Message[M]:
        return self.message


class Messages(abc.ABC):
    pass


Messages.register(Message)
Messages.register(Envelope)

__all__ = ('pmessage', 'json_pmessage', 'Sendable', 'Message', 'Msg', 'Envelope', 'ToMachine', 'Messages')
