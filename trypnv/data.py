import pyrsistent  # type: ignore


def field(tpe, **kw):
    return pyrsistent.field(type=tpe, mandatory=True, **kw)


class Data(pyrsistent.PRecord):
    pass

__all__ = ('field', 'Data')
