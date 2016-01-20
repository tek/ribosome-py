import pyrsistent  # type: ignore

from tryp import List, Empty, Maybe, Map

from typing import Callable


def field(tpe, **kw):
    return pyrsistent.field(type=tpe, mandatory=True, **kw)


def list_field(**kw):
    return field(List, initial=List(), factory=List.wrap, **kw)


def dfield(default, **kw):
    return field(type(default), initial=default, **kw)


def maybe_field(tpe, initial=Empty(), **kw):
    err = 'must be Maybe[{}]'.format(tpe)
    inv = lambda a: (not a.exists(lambda b: not isinstance(b, tpe)), err)
    return field(Maybe, initial=initial, invariant=inv, **kw)


class Data(pyrsistent.PRecord):
    sub_states = field(Map, initial=Map())

    def sub_state(self, name, default: Callable):
        return self.sub_states.get_or_else(name, default)

    def with_sub_state(self, name, state):
        new_states = self.sub_states + (name, state)
        return self.set(sub_states=new_states)

__all__ = ('field', 'Data', 'list_field', 'dfield', 'maybe_field')
