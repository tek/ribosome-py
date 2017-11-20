import abc
import functools
import time
import inspect
from typing import Optional, Any, TypeVar, Type, Callable, Generic
from types import FunctionType, SimpleNamespace

from amino import Map, List, Empty, Just, __, L, Maybe, _, Lists, Nothing
from amino.dat import Dat, DatMeta

from ribosome.record import any_field, dfield, list_field, field, RecordMeta, Record, bool_field

_machine_attr = '_machine'
_message_attr = '_message'
_prio_attr = '_prio'
_dyn_attr = '_dyn'
default_prio = 0.5
fallback_prio = 0.3
override_prio = 0.8


def _field_namespace(fields, opt_fields, varargs):
    namespace = Map()
    for fname in fields:
        namespace[fname] = any_field()
    for fname, val in opt_fields:
        namespace[fname] = any_field(initial=val)
    if varargs:
        namespace[varargs] = list_field()
    return namespace


def _init_field_metadata(inst):
    def set_missing(name, default):
        if not hasattr(inst, name):
            setattr(inst, name, default)
    List(
        ('_field_varargs', None),
        ('_field_order', []),
        ('_field_count_min', 0),
    ).map2(set_missing)


def _update_field_metadata(inst, fields, opt_fields, varargs):
    if varargs is not None:
        inst._field_varargs = varargs
    inst._field_order += list(fields) + List(*opt_fields).map(__[0])
    inst._field_count_min += len(fields)
    inst._field_count_max = (
        Empty() if inst._field_varargs
        else Just(inst._field_count_min + len(opt_fields)))


class Sendable:

    @abc.abstractproperty
    def msg(self) -> 'Message':
        ...


class PMessageMeta(RecordMeta, abc.ABCMeta):

    def __new__(cls, name, bases, namespace, fields=[], opt_fields=[], varargs=None, skip_fields=False, **kw):
        ''' create a subclass of PRecord
        **fields** is a list of strings used as names of mandatory PRecord fields
        **opt_fields** is a list of (string, default) used as fields with initial values
        the order of the names is preserved in **_field_order**.
        **varargs** is an optional field name where unmatched args are stored.
        **skip_fields** indicates that the current class is a base class (like PMessage). If those classes were
        processed here, all their subclasses would share the metadata, and get all fields set by other subclasses.
        **_field_count_min** and **_field_count_max** are used by `MessageCommand`
        '''
        ns = Map() if skip_fields else _field_namespace(fields, opt_fields, varargs)
        inst = super().__new__(cls, name, bases, ns ** namespace, **kw)
        if not skip_fields:
            _init_field_metadata(inst)
            _update_field_metadata(inst, fields, opt_fields, varargs)
        return inst

    def __init__(cls, name, bases, namespace, **kw):
        super().__init__(name, bases, namespace)

M = TypeVar('M', bound='PMessage')
A = TypeVar('A', bound='Message')


@functools.total_ordering
class PMessage(Record, Sendable, metaclass=PMessageMeta, skip_fields=True):
    ''' Interface between vim commands and state.
    Provides a constructor that allows specification of fields via positional arguments.
    '''
    time = field(float)
    prio = dfield(0.5)
    bang = bool_field()
    range = any_field(initial=0)

    def __new__(cls, *args, **kw):
        count = len(cls._field_order)
        sargs, vargs = args[:count], args[count:]
        vmap = Map({cls._field_varargs: vargs}) if cls._field_varargs else Map()
        field_map = vmap ** Map(zip(cls._field_order, sargs))
        ext_kw = field_map ** kw + ('time', time.time())
        return super().__new__(cls, **ext_kw)

    def __init__(self, *a: Any, **kw: Any) -> None:
        pass

    @classmethod
    def from_msg(cls: Type[M], other: 'PMessage') -> Callable[..., M]:
        return lambda *a, **kw: cls(*a, bang=other.bang, range=other.range, **kw)

    @property
    def pub(self):
        return Publish(self)

    def __lt__(self, other):
        if isinstance(other, PMessage):
            if self.prio == other.prio:
                return self.time < self.time
            else:
                return self.prio < other.prio
        else:
            return True

    def at(self, prio):
        return self.set(prio=float(prio))

    @property
    def _str_extra(self) -> List[Any]:
        return Lists.wrap(self._field_order) // L(Maybe.getattr)(self, _) + self.bang.l('bang!')

    @property
    def msg(self) -> Sendable:
        return self


def message_definition_module() -> Optional[str]:
    return inspect.currentframe().f_back.f_back.f_globals['__name__']


def pmessage(name: str, *fields: str, mod: str=None, **kw: Any) -> Type[M]:
    module = mod or message_definition_module()
    return PMessageMeta(name, (PMessage,), dict(__module__=module), fields=fields, **kw)


def json_pmessage(name, *fields, mod=None, **kw):
    opt = (('options', Map()),)
    module = mod or message_definition_module()
    return pmessage(name, *fields, opt_fields=opt, mod=module, **kw)


class Publish(PMessage, fields=('message',)):

    def __str__(self):
        return 'Publish({})'.format(str(self.message))


class Message(Generic[A], Dat[A], Sendable):

    def at(self, prio: float) -> 'Envelope[A]':
        return Envelope(self, time.time(), prio, Nothing)

    @property
    def envelope(self) -> 'Envelope[A]':
        return self.at(0.5)

    @property
    def pub(self) -> 'Envelope[A]':
        return self.envelope

    def to(self, target: str) -> 'Envelope[A]':
        return self.envelope.copy(recipient=Just(target))

    @property
    def msg(self) -> 'Message':
        return self


def message_init(fields: Map[str, Type], glob: dict) -> FunctionType:
    name = 'message_init__'
    params = fields.map2(lambda n, t: f'{n}: {t.__name__}')
    assign = fields.k.map(lambda a: f'self.{a} = {a}')
    code = f'''\
def __init__(self, {params.join_comma}) -> None:
    {assign.join_lines}
globals()['{name}'] = __init__
    '''
    exec(code, glob)
    init = glob[name]
    del glob[name]
    return init


class MsgMeta(DatMeta):

    @classmethod
    def __prepare__(cls, name: str, bases: tuple, glob: dict=None, **kw: Any) -> dict:
        globs = glob or inspect.currentframe().f_back.f_globals
        return dict(__init__=message_init(Map(kw), globs)) if kw else dict()

    def __new__(cls, name: str, bases: tuple, namespace: SimpleNamespace, **kw: Any) -> type:
        return super().__new__(cls, name, bases, namespace)


class Msg(Generic[A], Message[A], metaclass=MsgMeta):
    pass


@functools.total_ordering
class Envelope(Generic[A], Dat['Envelope[A]'], Sendable):

    @staticmethod
    def from_sendable(s: Sendable) -> 'Envelope[A]':
        return s if isinstance(s, Envelope) else Envelope.default(s)

    @staticmethod
    def default(m: Message[A]) -> 'Envelope[A]':
        return Envelope(m, time.time(), 0.5, Nothing)

    def __init__(self, message: Message[A], time: float, prio: float, recipient: Maybe[str]) -> None:
        self.message = message
        self.time = time
        self.prio = prio
        self.recipient = recipient

    def at(self, prio: float) -> 'Envelope[A]':
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


class ToMachine(Generic[A], Dat['ToMachine[A]'], Sendable):

    def __init__(self, envelope: Envelope[A], target: str) -> None:
        self.envelope = envelope
        self.target = target

    @property
    def message(self) -> Message[A]:
        return self.envelope.message

    @property
    def msg(self) -> Message[A]:
        return self.message


class Messages(abc.ABC):
    pass


Messages.register(Message)
Messages.register(PMessage)
Messages.register(Envelope)

__all__ = ('pmessage', 'PMessage', 'json_pmessage', 'Publish')
