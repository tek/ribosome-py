import pyrsistent

from tryp import List, Empty, Maybe, Boolean, _, Map
from tryp.lazy import LazyMeta, Lazy, lazy
from tryp.lazy_list import LazyList


def any_field(**kw):
    return pyrsistent.field(mandatory=True, **kw)


def field(tpe, **kw):
    return any_field(type=tpe, **kw)


def list_field(**kw):
    return field(List, initial=List(), factory=List.wrap, **kw)


def lazy_list_field(**kw):
    return field(LazyList, initial=LazyList([]), factory=LazyList, **kw)


def dfield(default, **kw):
    return field(type(default), initial=default, **kw)


def maybe_field(tpe, initial=Empty(), **kw):
    err = 'must be Maybe[{}]'.format(tpe)
    inv = lambda a: (not a.exists(lambda b: not isinstance(b, tpe)), err)
    return field(Maybe, initial=initial, invariant=inv, **kw)


def bool_field(**kw):
    return field(Boolean, factory=Boolean.wrap, **kw)


def map_field(**kw):
    return dfield(Map(), **kw)


class FieldMutator(object):

    def __init__(self, name: str, target: 'Record') -> None:
        self.name = name
        self.target = target


class FieldSetter(FieldMutator):

    def __call__(self, value):
        return self.target.set(**{self.name: value})


class FieldAppender(FieldMutator):

    def __call__(self, value):
        return self.target.mod(self.name, _ + value)


class FieldAppender1(FieldMutator):

    def __call__(self, value):
        return self.target.mod(self.name, _ + List(value))


class FieldProxy(FieldMutator):

    def __init__(self, target: 'Record', tpe: type) -> None:
        self.target = target
        self.tpe = tpe

    def __getattr__(self, name):
        return self(name)

    def __call__(self, name):
        return self.tpe(name, self.target)


class RecordMeta(LazyMeta, pyrsistent.PClassMeta):
    pass


class Record(pyrsistent.PClass, Lazy, metaclass=RecordMeta):

    @lazy
    def setter(self):
        return FieldProxy(self, FieldSetter)

    def _lens_setattr(self, name, value):
        return self.setter(name)(value)

    @lazy
    def append(self):
        return FieldProxy(self, FieldAppender)

    @lazy
    def append1(self):
        return FieldProxy(self, FieldAppender1)

    def mod(self, name: str, modder):
        par = {name: modder(getattr(self, name))}
        return self.set(**par)

__all__ = ('Record', 'field', 'list_field', 'dfield', 'maybe_field',
           'bool_field', 'any_field')
