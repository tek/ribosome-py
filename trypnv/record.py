import pyrsistent  # type: ignore

from tryp import List, Empty, Maybe, Boolean
from tryp.lazy import LazyMeta, Lazy


def any_field(**kw):
    return pyrsistent.field(mandatory=True, **kw)


def field(tpe, **kw):
    return any_field(type=tpe, **kw)


def list_field(**kw):
    return field(List, initial=List(), factory=List.wrap, **kw)


def dfield(default, **kw):
    return field(type(default), initial=default, **kw)


def maybe_field(tpe, initial=Empty(), **kw):
    err = 'must be Maybe[{}]'.format(tpe)
    inv = lambda a: (not a.exists(lambda b: not isinstance(b, tpe)), err)
    return field(Maybe, initial=initial, invariant=inv, **kw)


def bool_field(**kw):
    return field(Boolean, factory=Boolean.wrap, **kw)


class FieldSetter(object):

    def __init__(self, name: str, target: 'Record') -> None:
        self.name = name
        self.target = target

    def __call__(self, value):
        return self.target.set(**{self.name: value})


class RecordMeta(LazyMeta, pyrsistent.PClassMeta):
    pass


class Record(pyrsistent.PClass, Lazy, metaclass=RecordMeta):

    def setter(self, name: str) -> FieldSetter:
        return FieldSetter(name, self)

    def mod(self, name: str, modder):
        par = { name: modder(getattr(self, name)) }
        return self.set(**par)

__all__ = ('Record', 'field', 'list_field', 'dfield', 'maybe_field',
           'bool_field', 'any_field')
