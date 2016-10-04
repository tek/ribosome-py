import uuid
import re
from typing import Callable

import pyrsistent

from lenses import Lens, lens

from amino import (List, Empty, Boolean, _, Map, Left, L, __, Either, Try,
                   Maybe, Just)
from amino.lazy import LazyMeta, Lazy, lazy
from amino.lazy_list import LazyList

from ribosome.logging import Logging


def any_field(**kw):
    return pyrsistent.field(mandatory=True, **kw)


def field(tpe, **kw):
    return any_field(type=tpe, **kw)


def _monad_type_field_inv(eff, tpe):
    def inv(a):
        if tpe is None:
            return True, ''
        else:
            bad = a.find(lambda b: not isinstance(b, tpe))
            bad_tpe = bad | ''
            err = 'must be {}[{}], found {}'.format(eff, tpe.__name__, bad_tpe)
            return not bad.present, err
    return inv


def list_field(tpe=None, initial=List(), **kw):
    return field(List, initial=initial, factory=List.wrap,
                 invariant=_monad_type_field_inv('List', tpe), **kw)


def lazy_list_field(**kw):
    return field(LazyList, initial=LazyList([]), factory=LazyList, **kw)


def dfield(default, **kw):
    return field(type(default), initial=default, **kw)


def maybe_field(tpe=None, initial=Empty(), **kw):
    return field(Maybe, initial=initial,
                 invariant=_monad_type_field_inv('Maybe', tpe), **kw)


def either_field(rtpe, ltpe=str, initial=Left('pristine'), **kw):
    err = 'must be Either[{}, {}]'.format(ltpe, rtpe)
    check = lambda t, a: (isinstance(a, t), err)
    inv = __.cata(L(check)(ltpe, _), L(check)(rtpe, _))
    return field(Either, initial=initial, invariant=inv, **kw)


def bool_field(initial=False, **kw):
    return field(Boolean, factory=Boolean.wrap, initial=Boolean(initial), **kw)


def map_field(**kw):
    return dfield(Map(), **kw)


def uuid_field():
    return field(uuid.UUID, initial=lambda: uuid.uuid4())


def _re_fact(ex: str):
    return Try(re.compile, ex) | re.compile('')


def re_field(**kw):
    return field(re._pattern_type, factory=_re_fact, **kw)


class FieldMutator(object):

    def __init__(self, name: str, target: 'Record') -> None:
        self.name = name
        self.target = target


class FieldSetter(FieldMutator):

    def __call__(self, value):
        return self.target.set(**{self.name: value})


class FieldModifier(FieldMutator):

    def __call__(self, f):
        return self.target.set(
            **{self.name: f(getattr(self.target, self.name))})


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

    @property
    def mandatory_fields(self):
        mand = lambda f: f.mandatory and f.initial.__class__ is object
        return Map(self._pclass_fields).valfilter(mand)

    @property
    def _field_data(self):
        return Map(self._pclass_fields).valmap(_.type)

    @property
    def _field_names(self):
        return List.wrap(self._pclass_fields.keys())

    @property
    def _field_names_no_uuid(self):
        return self._field_names - 'uuid'


class Record(pyrsistent.PClass, Lazy, Logging, metaclass=RecordMeta):

    @classmethod
    def args_from_opt(cls, opt: Map):
        def may_arg(name, value):
            return name, Just(value)
        def list_arg(name, value):
            return name, value
        def regular_arg(name, value):
            return name, value
        def arg(name, types):
            cb = (may_arg if Maybe in types else list_arg if List in types else
                  regular_arg)
            return opt.get(name) / L(cb)(name, _)
        return Map(cls._field_data.map2(arg).join)

    @classmethod
    def from_opt(cls, opt: Map) -> Maybe:
        return cls(**cls.args_from_opt(opt))

    def update_from_opt(self, opt: Map):
        return self.set(**self.args_from_opt(opt))

    @property
    def _name(self):
        return self.__class__.__name__

    @property
    def _str_name(self):
        return self._name

    @property
    def _str_extra(self):
        return List()

    def __str__(self):
        return '{}({})'.format(self._str_name, self._str_extra.mk_string(', '))

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

    @lazy
    def modder(self):
        return FieldProxy(self, FieldModifier)

    def mod(self, name: str, modder):
        par = {name: modder(getattr(self, name))}
        return self.set(**par)

    @property
    def _fields_no_uuid(self):
        return type(self)._field_names_no_uuid / (lambda a: getattr(self, a))

    def __eq__(self, other):
        return (
            type(self) == type(other) and
            type(self)._field_names_no_uuid
            .forall(lambda a: getattr(self, a) == getattr(other, a))
        )

    def __hash__(self):
        return sum(self._fields_no_uuid / hash)

    def attr_lens(self, attr: Callable[..., List], sub: Callable[..., Lens]):
        return attr(self).find_lens(sub) / attr(lens()).add_lens

    def attr_lens_pred(self, attr: Callable[..., List],
                       pred: Callable[..., bool]):
        return attr(self).find_lens_pred(pred) / attr(lens()).add_lens

__all__ = ('Record', 'field', 'list_field', 'dfield', 'maybe_field',
           'bool_field', 'any_field')
