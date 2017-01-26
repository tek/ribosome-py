import re
import uuid
import json
from typing import Callable

import pyrsistent

from lenses import Lens, lens

from toolz import merge

from amino import (List, Empty, Boolean, _, Map, Left, L, __, Either, Try,
                   Maybe, Just, Path, I)
from amino.lazy import LazyMeta, Lazy, lazy
from amino.lazy_list import LazyList
from amino.tc.optional import Optional
from amino.tc.foldable import Foldable

from ribosome.logging import Logging


def any_field(**kw):
    return pyrsistent.field(mandatory=True, **kw)


def field(tpe, **kw):
    return any_field(type=tpe, **kw)


def _foldable_type_field_inv(eff, tpe):
    def inv(a):
        atpe = type(a)
        if tpe is None:
            return True, ''
        elif not Foldable.exists_instance(atpe):
            return False, '{} does not have a Foldable'.format(atpe)
        else:
            bad = a.find(lambda b: not isinstance(b, tpe))
            bad_tpe = bad | ''
            err = 'must be {}[{}], found {}'.format(eff, tpe.__name__, bad_tpe)
            return not bad.present, err
    return inv


def list_field(tpe=None, initial=List(), **kw):
    return field(List, initial=initial, factory=List.wrap,
                 invariant=_foldable_type_field_inv('List', tpe), **kw)


def lazy_list_field(**kw):
    return field(LazyList, initial=LazyList([]), factory=LazyList, **kw)


def dfield(default, **kw):
    return field(type(default), initial=default, **kw)


def maybe_factory(fact, tpe):
    def f(val):
        return val / (lambda v: v if isinstance(v, tpe) else fact(v))
    return f


def maybe_field(tpe=None, factory=None, initial=Empty(), **kw):
    fact = I if factory is None or tpe is None else maybe_factory(factory, tpe)
    return field(Maybe, initial=initial,
                 invariant=_foldable_type_field_inv('Maybe', tpe),
                 factory=fact, **kw)


def either_field(rtpe, ltpe=str, initial=Left('pristine'), **kw):
    err = 'must be Either[{}, {}]'.format(ltpe, rtpe)
    check = lambda t, a: (isinstance(a, t), err)
    inv = __.cata(L(check)(ltpe, _), L(check)(rtpe, _))
    return field(Either, initial=initial, invariant=inv, **kw)


class OptionalInvariant:

    def __init__(self, tpe) -> None:
        self.tpe = tpe

    def __call__(self, a):
        atpe = type(a)
        return (
            _foldable_type_field_inv('Optional', self.tpe)(a)
            if Optional.exists_instance(atpe) else
            (False, '{} has no Optional'.format(atpe))
        )


class OptionalFactory:

    def __init__(self, factory, tpe) -> None:
        self.factory = factory
        self.tpe = tpe

    @property
    def fact(self):
        return maybe_factory(self.factory, self.tpe)

    def __call__(self, a):
        return a if self.factory is None or self.tpe is None else self.fact(a)


def optional_field(tpe=None, factory=None, initial=Empty(), **kw):
    return any_field(initial=initial, factory=OptionalFactory(factory, tpe),
                     invariant=OptionalInvariant(tpe), **kw)


def bool_field(initial=False, **kw):
    return field(Boolean, factory=Boolean.wrap, initial=Boolean(initial), **kw)


def map_field(**kw):
    return dfield(Map(), **kw)


def uuid_field():
    return field(uuid.UUID, initial=lambda: uuid.uuid4())


def int_field(**kw):
    return field(int, **kw)


def float_field(**kw):
    return field(float, **kw)


def str_field(**kw):
    return field(str, **kw)


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
    def _field_map(self):
        return Map(self._pclass_fields)

    @property
    def _field_data(self):
        return self._field_map.valmap(_.type)

    @property
    def _field_names(self):
        return List.wrap(self._pclass_fields.keys())

    @property
    def _field_names_no_uuid(self):
        return self._field_names - 'uuid'


class Record(pyrsistent.PClass, Lazy, Logging, metaclass=RecordMeta):

    @classmethod
    def args_from_opt(cls, opt: Map):
        def may_arg(name, field, value):
            ctor = field.factory
            return name, ctor(Just(value))
        def list_arg(name, field, value):
            return name, value
        def regular_arg(name, field, value):
            return name, value
        def arg(name, field):
            cb = (
                may_arg if Maybe in field.type else
                list_arg if List in field.type else
                may_arg if isinstance(field.factory, OptionalFactory) else
                regular_arg
            )
            return opt.get(name) / L(cb)(name, field, _)
        return Map(cls._field_map.map2(arg).join)

    @classmethod
    def from_opt(cls, opt: Map):
        return cls(**cls.args_from_opt(opt))

    @classmethod
    def from_attr(cls, arg):
        return lambda a, **kw: cls(**{arg: a}, **kw)

    def set_from_opt(self, opt: Map):
        return self.set(**self.args_from_opt(opt))

    def update_from_opt(self, opt: Map):
        return self.set(**self.args_from_opt(opt))

    @property
    def _name(self):
        return self.__class__.__name__

    @property
    def _str_name(self):
        return self._name

    @property
    def _str_extra(self) -> List:
        return List()

    @property
    def _str_extra_named(self) -> Map:
        return Map()

    def __str__(self):
        extra_named = self._str_extra_named.map2('{}={}'.format)
        return '{}({})'.format(self._str_name,
                               (self._str_extra + extra_named).join_comma)

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

    @property
    def __path__(self):
        cls = self.__class__
        return '{}.{}'.format(cls.__module__, cls.__name__)

    def to_map(self):
        return Map(type(self)._field_names_no_uuid.apzip(L(getattr)(self, _)))

    @property
    def json(self):
        return merge(self.to_map(), dict(__type__=self.__path__))


def _decode_json_obj(obj):
    m = Map(obj)
    return (
        m.get('__type__') /
        L(Either.import_path)(_).get_or_raise.from_opt(m) |
        m
    )


class EncodeJson(json.JSONEncoder):

    def default(self, obj):
        return (
            obj.json
            if hasattr(obj, 'json') else
            str(obj)
            if isinstance(obj, (uuid.UUID, Path)) else
            super().default(obj)
        )


def json_err(task, data, err):
    return 'error {}coding json: {}\ndata: {}'.format(task, err, data)


def _encode_json(data):
    return EncodeJson().encode(data)


def _decode_json(data):
    return json.loads(data, object_hook=_decode_json_obj)


def _code_json(data, handler, prefix):
    return Try(handler, data).lmap(L(json_err)(prefix, data, _))


def encode_json(data):
    return _code_json(data, _encode_json, 'en')


def decode_json(data):
    return _code_json(data, _decode_json, 'de')

__all__ = ('Record', 'field', 'list_field', 'dfield', 'maybe_field',
           'bool_field', 'any_field', 'encode_json', 'decode_json',
           'int_field', 'uuid_field', 'map_field', 'either_field', 'str_field',
           'float_field')
