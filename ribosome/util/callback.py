import abc
import re

from amino import Maybe, Either, __, Left, F, Right

from ribosome.logging import Logging


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

_py_callback_re = re.compile('^py:(.+)')
_vim_callback_re = re.compile('^vim:(.+)')
_special_callback_re = re.compile('^s:(.+)')


def _cb_err(data):
    return 'invalid callback string: {}'.format(data)


def parse_python_callback(data: str):
    return (
        Maybe(_py_callback_re.match(data)) /
        __.group(1) /
        Either.import_path
    ).to_either(_cb_err(data))


def parse_vim_callback(data: str):
    return Left(_cb_err(data))


def parse_special_callback(data: str):
    return (
        Maybe(_special_callback_re.match(data)) /
        __.group(1) /
        SpecialCallback /
        Right
    ).to_either(_cb_err(data))


def parse_callback_spec(data: str):
    if not isinstance(data, str):
        return Left('callback spec must be str, got {}'.format(type(data)))
    else:
        return (
            parse_python_callback(data)
            .or_else(F(parse_vim_callback, data))
            .or_else(F(parse_special_callback, data))
        )

__all__ = ('VimCallback', 'parse_callback_spec')
