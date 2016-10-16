import re
import abc
from typing import Callable

from amino import Maybe, Either, __, Right, L, List, _, Map, Try

from ribosome.logging import Logging
from ribosome.nvim import NvimFacade


class VimCallback(Logging, metaclass=abc.ABCMeta):

    def __init__(self, target) -> None:
        self.target = target
        self.vim = self.target.root

    @abc.abstractmethod
    def __call__(self, data):
        ...


class SpecialCallback:

    def __init__(self, name) -> None:
        self.name = name

    def __str__(self):
        return self.name


class CallbackSpec(Logging, metaclass=abc.ABCMeta):

    def __init__(self, spec) -> None:
        self.spec = spec

    @abc.abstractmethod
    def func(self, vim: NvimFacade) -> Either[str, Callable]:
        ...

    def __call__(self, vim: NvimFacade, *a):
        return self.func(vim) // __(*a)

    def __str__(self):
        return '{}({})'.format(self.__class__.__name__, self.spec)


class PythonCallbackSpecBase(CallbackSpec):

    def _inst(self, vim, name):
        return (Try(name, vim)
                if isinstance(name, type) and issubclass(name, VimCallback)
                else Right(name))

    @abc.abstractmethod
    def _func(self):
        ...

    def func(self, vim):
        return self._func // L(self._inst)(vim, _)


class PythonCallbackSpec(PythonCallbackSpecBase):

    @property
    def _func(self):
        return Either.import_path(self.spec)


class StrictPythonCallbackSpec(PythonCallbackSpecBase):

    @property
    def _func(self):
        return Right(self.spec)


class VimFuncCallbackSpec(CallbackSpec):

    def func(self, vim):
        return Right(L(vim.call)(self.spec))


class VarCallbackSpec(CallbackSpec):

    def func(self, vim):
        return Right(L(vim.vars)(self.spec))

_py_callback_re = re.compile('^py:(.+)')
_vim_callback_re = re.compile('^vim:(.+)')
_var_callback_re = re.compile('^var:(.+)')
_special_callback_re = re.compile('^s:(.+)')

_callback_res = List(
    (_py_callback_re, PythonCallbackSpec),
    (_vim_callback_re, VimFuncCallbackSpec),
    (_var_callback_re, VarCallbackSpec),
)


def _cb_err(data):
    return 'invalid callback string: {}'.format(data)


def parse_callback(data: str, rex, tpe: type):
    return (
        Maybe(rex.match(data)) /
        __.group(1) /
        tpe
    )


def parse_special_callback(data, special: Map) -> Maybe[CallbackSpec]:
    return (
        Maybe(_special_callback_re.match(data)) /
        __.group(1) //
        special.get /
        StrictPythonCallbackSpec
    )


def parse_callback_spec(data: str, special=Map()) -> Maybe[CallbackSpec]:
    spec = special.empty.no.flat_m(L(parse_special_callback)(data, special))
    other = lambda: _callback_res.flat_map2(L(parse_callback)(data, _, _)).head
    return spec.o(other).to_either(_cb_err(data))

__all__ = ('VimCallback', 'parse_callback_spec')
