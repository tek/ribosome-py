import pyrsistent  # type: ignore

from tryp import List, Empty, Maybe, Map

def field(tpe, **kw):
    return pyrsistent.field(type=tpe, mandatory=True, **kw)


def list_field(**kw):
    return field(List, initial=List(), factory=List.wrap, **kw)


def dfield(default, **kw):
    return field(type(default), initial=default, **kw)


def maybe_field(tpe, initial=Empty(), **kw):
    inv = lambda a: not a.exists(lambda b: not isinstance(b, tpe))
    return field(Maybe, initial=initial, invariant=inv, **kw)


class Data(pyrsistent.PRecord):
    pass

__all__ = ('field', 'Data', 'list_field', 'dfield', 'maybe_field')
