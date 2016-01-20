from typing import TypeVar, Callable, Any, Generic
from pathlib import Path
from functools import singledispatch  # type: ignore
import threading
import concurrent.futures
from contextlib import contextmanager
import asyncio
from datetime import datetime
import abc

import neovim
from neovim.api import NvimError

from fn import _, F  # type: ignore

from pyrsistent import PRecord

from tek.tools import camelcaseify  # type: ignore

import tryp
from tryp import Maybe, may, List, Map, Boolean, Empty, Just, __
from tryp.either import Either, Right, Left

from trypnv.data import dfield
from trypnv.logging import Logging


def squote(text):
    return text.replace("'", "''")


def dquote(text):
    return text.replace('"', '\\"')


def quote(text):
    return dquote(squote(text))

A = TypeVar('A')


def echo(text, cmd='echom', prefix=Empty()):
    pre = prefix.map(_ + ': ') | ''
    return '{} "{}{}"'.format(cmd, pre, dquote(text))


def echohl(text, hl, prefix=Empty()):
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


class NvimComponent(Logging):

    def __init__(self, vim, target, prefix: str) -> None:
        self.vim = vim
        self.target = target
        self.prefix = prefix
        self._vars = set()  # type: set

    @property
    def loop(self):
        return self.vim.session._session._async_session._msgpack_stream\
            ._event_loop._loop

    def delay(self, f, timeout):
        threading.Timer(
            1.0, lambda: self.vim.session.threadsafe_call(f)).start()

    def async(self, f: Callable[['NvimFacade'], Any]):
        result = concurrent.futures.Future()
        self.vim.session.threadsafe_call(lambda: result.set_result(f(self)))
        return result.result()

    @contextmanager
    def main_event_loop(self):
        main = self.async(lambda v: asyncio.get_event_loop())
        fut = asyncio.Future(loop=main)
        self.vim.session.threadsafe_call(lambda: main.run_until_complete(fut))
        yield
        main.call_soon_threadsafe(lambda: fut.set_result(True))

    @property
    def proxy(self):
        return AsyncVimProxy(self)

    def prefixed(self, name: str):
        return '{}_{}'.format(self.prefix, name)

    @may
    def var(self, name) -> Maybe[str]:
        v = self.target.vars.get(name)
        if v is None:
            self.log.debug('variable not found: {}'.format(name))
        return decode(v)

    def set_var(self, name, value):
        try:
            self.target.vars[name] = value
        except:
            msg = 'setting vim variable {} to {}'
            self.log.exception(msg.format(name, value))
        else:
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

    def ppathl(self, name: str) -> Maybe[Path]:
        return self.pl(name)\
            .map(lambda l: l.map(lambda a: Path(a).expanduser()))

    def dir(self, name: str) -> Maybe[Path]:
        var = self.path(name)
        val = var.filter(_.call('is_dir'))
        if not val.is_just:
            msg = 'g:{} is not a directory ({})'
            self.log.error(msg.format(name, var))
        return val

    def pdir(self, name: str) -> Maybe[Path]:
        return self.dir(self.prefixed(name))

    def clean(self):
        for name in self._vars:
            del self.target.vars[name]
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
        v = self.target.options.get(name)
        if v is None:
            self.log.debug('variable not found: {}'.format(name))
        return decode(v)

    def set_option(self, name: str, value):
        try:
            self.target.options[name] = value
        except NvimError as e:
            self.log.error(e)

    def options(self, name: str):
        return self.typed(str, self.option(name))

    def set_options(self, name: str, value):
        return self.set_option(name, str(value))

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
        self.target.options[name] = ','.join(value)

    def optionb(self, name: str):
        return self.typed(bool, self.option(name))

    def set_optionb(self, name: str, value):
        return self.set_option(name, bool(value))

    def cmd(self, line: str):
        return self.vim.command(line, async=True)

    def cmd_sync(self, line: str):
        return self.vim.command(line, async=False)


class HasBuffer(NvimComponent, metaclass=abc.ABCMeta):

    @property
    def buffer(self):
        return Buffer(self.vim, self._internal_buffer, self.prefix).proxy

    @abc.abstractproperty
    def _internal_buffer(self):
        ...


class HasBuffers(HasBuffer):

    @property
    def buffers(self):
        return List(*self._internal_buffers)\
            .map(lambda a: Buffer(self.vim, a, self.prefix).proxy)

    @property
    def _internal_buffers(self):
        return self.vim.buffers

    def bufnew(self):
        self.cmd('bufnew')
        return self.buffer


class HasWindow(HasBuffer):

    @property
    def window(self):
        return Window(self.vim, self._internal_window, self.prefix).proxy

    @abc.abstractproperty
    def _internal_window(self):
        ...

    @property
    def _internal_buffer(self):
        return self._internal_window.buffer


class HasWindows(HasBuffers, HasWindow):

    @property
    def windows(self):
        return List(*self._internal_windows)\
            .map(lambda a: Window(self.vim, a, self.prefix).proxy)

    @property
    def _internal_windows(self):
        return self.vim.windows


class HasTab(HasWindow):

    @property
    def tab(self):
        return Tab(self.vim, self._internal_tab, self.prefix).proxy

    @abc.abstractproperty
    def _internal_tab(self):
        ...

    @property
    def _internal_window(self):
        return self._internal_tab.window


class HasTabs(HasTab):

    @property
    def tabs(self):
        return List(*self._internal_tabs)\
            .map(lambda a: Tab(self.vim, a, self.prefix).proxy)

    @property
    def _internal_tabs(self):
        return self.vim.tabpages

    def tabnew(self):
        self.cmd('tabnew')
        return self.tab


class Buffer(HasWindow):

    @property
    def _internal_buffer(self):
        return self.target

    @property
    def _internal_window(self):
        return self.window

    @property
    def modified(self):
        return self.option('modified').contains(True)

    def set_content(self, text):
        self.target[:] = text


class Window(HasTab):

    @property
    def _internal_buffer(self):
        return self.target.buffer

    @property
    def _internal_tab(self):
        return self.tabpage

    @property
    def _internal_window(self):
        return self.target

    def reload(self):
        self.focus()
        if not self.buffer.modified:
            self.cmd('silent edit')

    # FIXME not constrained to visible tab
    def focus(self):
        self.vim.current.window = self.target


class Tab(HasWindows):

    @property
    def _internal_window(self):
        return self.target.window


class NvimFacade(HasTabs, HasWindows, HasBuffers, HasTab):

    def __init__(self, vim: neovim.Nvim, prefix: str) -> None:
        super(NvimFacade, self).__init__(vim, vim, prefix)

    def runtime(self, path: str):
        return self.cmd('runtime! {}.vim'.format(path))

    def echo(self, text: str):
        self.cmd(echo(text, 'echo', prefix=Empty()))

    def echom(self, text: str):
        self.cmd(echo(text, prefix=Just(self.prefix)))

    def echohl(self, hl: str, text: str):
        self.cmd(echohl(text, hl, prefix=Just(self.prefix)))

    def echowarn(self, text: str):
        self.echohl('WarningMsg', text)

    def echoerr(self, text: str):
        self.echohl('ErrorMsg', text)

    def multi_line_info(self, text: List[str]):
        ''' as a workaround for possible bug in embedded nvim,
        only write in bulk when in production
        '''
        if tryp.integration_test:
            text.foreach(self.log.info)
        else:
            self.log.info('\n'.join(text))

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
    def _internal_tab(self):
        return self.current.tabpage

    @property
    def _internal_window(self):
        return self.current.window

    @property
    def _internal_buffer(self):
        return self.current.buffer

    @property
    def modified(self):
        return self.buffer.modified

    def reload_window(self):
        self.window.reload()

    def reload_windows(self):
        self.windows.foreach(__.reload())

B = TypeVar('B')


class NvimIO(Generic[A]):

    def __init__(self, apply: Callable[[NvimComponent], A]):
        self._apply = apply

    def unsafe_perform_io(self, vim) -> Either[Exception, A]:
        try:
            return Right(self._apply(vim))
        except Exception as e:
            return Left(e)

    def flat_map(self, f: Callable[[A], 'NvimIO[B]']):
        g = lambda v: f(self._apply(v))._apply(v)
        return NvimIO(g)

    __floordiv__ = flat_map

    def map(self, f: Callable[[A], B]):
        return NvimIO(F(self._apply) >> f)

    __truediv__ = map

    def effect(self, f: Callable[[A], Any]):
        def wrap(v):
            ret = self._apply(v)
            f(ret)
            return ret
        return NvimIO(wrap)

    __mod__ = effect


class AsyncVimCallProxy(object):

    def __init__(self, vim, name):
        self.vim = vim
        self.name = name

    def __call__(self, *a, **kw):
        return self.vim.async(lambda v: getattr(v, self.name)(*a, **kw))


class AsyncVimProxy(object):

    def __init__(self, vim):
        self.vim = vim
        self.vim_tpe = type(vim)

    def __getattr__(self, name):
        if threading.current_thread() != threading.main_thread():
            return self.async_relay(name)
        else:
            return getattr(self.vim, name)

    def async_relay(self, name):
        if (hasattr(self.vim_tpe, name) and
                isinstance(getattr(self.vim_tpe, name), property)):
            return self.vim.async(lambda v: getattr(v, name))
        elif hasattr(self.vim, name):
            return AsyncVimCallProxy(self.vim, name)
        else:
            return getattr(self.vim, name)

    @property
    def current_buffer(self):
        return self.async_relay('current_buffer').proxy

    @property
    def buffers(self):
        return self.async_relay('buffers').map(_.proxy)


class Buffer(NvimComponent):
    pass


class Flags(object):

    def __init__(self, vim: NvimFacade, prefix: bool) -> None:
        self.vim = vim
        self.prefix = prefix

    def get(self, name, default=False):
        v = (self.vim.pvar(name) if self.prefix else self.vim.var(name))\
            .get_or_else(default)
        return Boolean(v)

    def __getattr__(self, name):
        return self.get(name)


class HasNvim(object):

    def __init__(self, vim: NvimFacade) -> None:
        self.vim = vim
        self.flags = Flags(vim, False)
        self.pflags = Flags(vim, True)


__all__ = ('NvimFacade', 'HasNvim')
