from typing import TypeVar
import logging
from pathlib import Path
from functools import singledispatch  # type: ignore
from threading import Timer  # type: ignore

from fn import _  # type: ignore

from tryp import Maybe, may, List, Map, Boolean

from tek.tools import camelcaseify  # type: ignore


def squote(text):
    return text.replace("'", "''")


def dquote(text):
    return text.replace('"', '\\"')


def quote(text):
    return dquote(squote(text))

A = TypeVar('A')


def echo(text, cmd='echom'):
    return '{} "{}"'.format(cmd, dquote(text))


def echohl(text, hl):
    return 'echohl {} | {} | echohl None'.format(hl, echo(text))


@singledispatch
def decode(value):
    return value


@decode.register(bytes)
def decode_bytes(value):
    return value.decode()


@decode.register(list)
def decode_list(value):
    return List.wrap(value).map(decode)


@decode.register(dict)
def decode_dict(value):
    return Map.wrap(value)\
        .keymap(decode)\
        .valmap(decode)


class NvimComponent(object):

    def __init__(self, comp, prefix: str) -> None:
        self.vim = comp
        self.prefix = prefix
        self._vars = set()  # type: set

    @property
    def log(self):
        return logging.root

    def prefixed(self, name: str):
        return '{}_{}'.format(self.prefix, name)

    @may
    def var(self, name) -> Maybe[str]:
        v = self.vim.vars.get(name)
        if v is None:
            self.log.debug('variable not found: {}'.format(name))
        return decode(v)

    def set_var(self, name, value):
        self.vim.vars[name] = value
        self._vars.add(name)

    def pvar(self, name) -> Maybe[str]:
        return self.var(self.prefixed(name))

    def set_pvar(self, name, value):
        self.set_var(self.prefixed(name), value)

    def path(self, name: str) -> Maybe[Path]:
        return self.var(name)\
            .map(lambda a: Path(a).expanduser())  # type: ignore

    def ppath(self, name: str) -> Maybe[Path]:
        return self.path(self.prefixed(name))

    def dir(self, name: str) -> Maybe[Path]:
        var = self.path(name)
        val = var.filter(_.call('is_dir'))
        if not val.isJust:
            msg = 'g:{} is not a directory ({})'
            self.log.error(msg.format(name, var))
        return val

    def pdir(self, name: str) -> Maybe[Path]:
        return self.dir(self.prefixed(name))

    def clean(self):
        for name in self._vars:
            del self.vim.vars[name]
        self._vars = set()

    def typed(self, tpe: type, value: Maybe[A]) -> Maybe[A]:
        @may
        def check(v: A):
            if isinstance(v, tpe):
                return v
            else:
                msg = 'invalid type {} for variable {} (wanted {})'.format(
                    type(v), v, tpe)
                self.log.error(msg)
        return value.flat_map(check)

    def s(self, name):
        return self.typed(str, self.var(name))

    def ps(self, name):
        return self.typed(str, self.pvar(name))

    def l(self, name):
        return self.typed(list, self.var(name))

    def pl(self, name):
        return self.typed(list, self.pvar(name))

    def d(self, name):
        return self.typed(dict, self.var(name))

    def pd(self, name):
        return self.typed(dict, self.pvar(name))

    @may
    def option(self, name: str) -> Maybe[str]:
        v = self.vim.options.get(name)
        if v is None:
            self.log.debug('variable not found: {}'.format(name))
        return v

    def set_option(self, name: str, value: str):
        self.vim.options[name] = str(value)

    def options(self, name: str):
        return self.typed(str, self.option(name))

    def optionl(self, name: str) -> List[str]:
        return self.options(name)\
            .map(lambda a: a.split(','))\
            .map(List.wrap)\
            .get_or_else(List())

    def amend_optionl(self, name: str, value):
        if not isinstance(value, list):
            value = List(value)
        new_value = (self.optionl(name) + list(map(str, value))).distinct
        self.set_optionl(name, new_value)

    def set_optionl(self, name: str, value: List[str]):
        self.vim.options[name] = ','.join(value)


class NvimFacade(NvimComponent):

    def cmd(self, line: str):
        return self.vim.command(line, async=True)

    def echo(self, text: str):
        self.cmd(echo(text, 'echo'))

    def echom(self, text: str):
        self.cmd(echo(text))

    def echohl(self, hl: str, text: str):
        self.cmd(echohl(text, hl))

    def echowarn(self, text: str):
        self.echohl('WarningMsg', text)

    def echoerr(self, text: str):
        self.echohl('ErrorMsg', text)

    def autocmd(self, name):
        self.cmd('silent doautocmd <nomodeline> User {}'.format(name))

    def pautocmd(self, name):
        self.autocmd('{}{}'.format(camelcaseify(self.prefix), name))

    def call(self, name, *a, **kw):
        return Maybe.from_call(self.vim.call, name, *a, **kw)

    @property
    def current(self):
        return self.vim.current

    @property
    def current_buffer(self):
        return Buffer(self.current.buffer, self.prefix)

    @property
    def buffers(self):
        return List(*self.vim.buffers).map(lambda a: Buffer(a, self.prefix))

    @property
    def loop(self):
        return self.vim.session._session._async_session._msgpack_stream\
            ._event_loop._loop

    def delay(self, f, timeout):
        Timer(1.0, lambda: self.vim.session.threadsafe_call(f)).start()


class Buffer(NvimComponent):
    pass


class Flags(object):

    def __init__(self, vim: NvimFacade, prefix: bool) -> None:
        self.vim = vim
        self.prefix = prefix

    def get(self, name, default=False):
        v = (self.vim.pvar(name) if self.prefix else self.vim.var(name))\
            .get_or_else(False)
        return Boolean(v)

    def __getattr__(self, name):
        return self.get(name)


class HasNvim(object):

    def __init__(self, vim: NvimFacade) -> None:
        self.vim = vim
        self.flags = Flags(vim, False)
        self.pflags = Flags(vim, True)


__all__ = ['NvimFacade', 'HasNvim']
