import abc
import functools
import time
import inspect
from typing import Optional, Any, TypeVar, Type, Callable

from amino import Map, List, Empty, Just, __, L, Maybe, _, Lists

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


class MessageMeta(RecordMeta, abc.ABCMeta):

    def __new__(cls, name, bases, namespace, fields=[], opt_fields=[], varargs=None, skip_fields=False, **kw):
        ''' create a subclass of PRecord
        **fields** is a list of strings used as names of mandatory PRecord fields
        **opt_fields** is a list of (string, default) used as fields with initial values
        the order of the names is preserved in **_field_order**.
        **varargs** is an optional field name where unmatched args are stored.
        **skip_fields** indicates that the current class is a base class (like Message). If those classes were processed
        here, all their subclasses would share the metadata, and get all fields set by other subclasses.
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

M = TypeVar('M', bound='Message')


@functools.total_ordering
class Message(Record, metaclass=MessageMeta, skip_fields=True):
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
    def from_msg(cls: Type[M], other: 'Message') -> Callable[..., M]:
        return lambda *a, **kw: cls(*a, bang=other.bang, range=other.range, **kw)

    @property
    def pub(self):
        return Publish(self)

    def __lt__(self, other):
        if isinstance(other, Message):
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


def message_definition_module() -> Optional[str]:
    return inspect.currentframe().f_back.f_back.f_globals['__name__']


def message(name: str, *fields: str, mod: str=None, **kw: Any) -> Type[M]:
    module = mod or message_definition_module()
    return MessageMeta(name, (Message,), dict(__module__=module), fields=fields, **kw)


def json_message(name, *fields, mod=None, **kw):
    opt = (('options', Map()),)
    module = mod or message_definition_module()
    return message(name, *fields, opt_fields=opt, mod=module, **kw)


class Publish(Message, fields=('message',)):

    def __str__(self):
        return 'Publish({})'.format(str(self.message))

__all__ = ('message', 'Message', 'json_message', 'Publish')
