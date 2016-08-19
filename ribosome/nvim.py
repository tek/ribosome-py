from typing import TypeVar, Callable, Any, Generic
from pathlib import Path
import threading
from concurrent import futures
from contextlib import contextmanager
import asyncio
import abc
from types import FunctionType
import inspect
import traceback

import neovim
from neovim.api import NvimError

from pyrsistent import PRecord

from amino.util.string import camelcaseify

import amino
from amino import Maybe, may, List, Map, Boolean, Empty, Just, __, _, F
from amino.either import Either, Right, Left
from amino.util.string import decode
from amino.anon import format_funcall

import ribosome
from ribosome.record import dfield
from ribosome.logging import Logging


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


class NvimComponent(Logging):

    def __init__(self, vim, target, prefix: str) -> None:
        if ribosome.in_vim and isinstance(target, (AsyncVimProxy,
                                                 NvimComponent)):
            msg = '{} created with non-native target {}'
            raise Exception(msg.format(self, target))
        self.vim = vim
        self.target = target
        self.prefix = prefix
        self._vars = set()  # type: set

    @property
    def loop(self):
        return self.vim.session._session._async_session._msgpack_stream\
            ._event_loop._loop

    def delay(self, f, timeout):
        cb = lambda: self.__run_on_main_thread(f)
        threading.Timer(1.0, cb).start()

    def async(self, f: Callable[['NvimComponent'], Any]):
        ''' run a callback function on the main thread and return its
        value (blocking). the callback receives 'self' as an argument.
        '''
        result = futures.Future()  # type: futures.Future
        cb = lambda: result.set_result(f(self))
        self._run_on_main_thread(cb)
        return result.result()

    def _run_on_main_thread(self, f: Callable[..., Any]):
        ''' run a callback function on the host's main thread
        '''
        frame = inspect.currentframe()  # type: ignore
        def dispatch():
            try:
                f()
            except NvimError as e:
                self._report_nvim_error(e, frame)
        self.vim.session.threadsafe_call(dispatch)

    def _report_nvim_error(self, err, frame):
        self.log.error('async vim call failed with \'{}\''.format(decode(err)))
        self.log.error(''.join(traceback.format_stack(frame)[:-5]))

    @contextmanager
    def main_event_loop(self):
        ''' run the asyncio main loop on vim's pyuv main thread, then
        yield the loop to the with statement in the current thread, and
        finally, gracefully stop the main loop.
        '''
        main = self.async(lambda v: asyncio.get_event_loop())
        fut = asyncio.Future(loop=main)
        self._run_on_main_thread(lambda: main.run_until_complete(fut))
        yield main
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
            .map(lambda l: l.map(Path).map(__.expanduser()))

    def dir(self, name: str) -> Maybe[Path]:
        var = self.path(name)
        val = var.filter(__.is_dir())
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

    def cmd(self, line: str, verbose=False, sync=False):
        ''' Wrap **Nvim.command**, default to async.
        **verbose** prevents the use of **silent**, which is used by
        default because headless nvim will deadlock if a command's
        output requires user input to proceed (e.g. multiline output)
        '''
        l = line if verbose else 'silent {}'.format(line)
        return self.vim.command(l, async=not sync)

    def cmd_sync(self, line: str, verbose=False):
        return self.cmd(line, verbose=verbose, sync=True)

    def cmd_output(self, line: str) -> List[str]:
        return List.wrap(self.vim.command_output(line).split('\n'))

    def vcmd(self, line: str, sync=False):
        return self.cmd(line, verbose=True, sync=sync)

    @property
    def syntax(self):
        return Syntax(self)


class HasBuffer(NvimComponent, metaclass=abc.ABCMeta):

    @property
    def buffer(self):
        return Buffer(self.vim, self._internal_buffer, self.prefix).proxy

    @abc.abstractproperty  # type: ignore
    def _internal_buffer(self):
        ...

    def __eq__(self, other):
        if hasattr(other, '_internal_buffer'):
            return self._internal_buffer == other._internal_buffer


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

    @abc.abstractproperty  # type: ignore
    def _internal_window(self):
        ...

    @property
    def _internal_buffer(self):
        return self.window._internal_buffer


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

    @abc.abstractproperty  # type: ignore
    def _internal_tab(self):
        ...

    @property
    def _internal_window(self):
        return self.tab._internal_window


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
        return self.window.target

    @property
    def modified(self):
        return self.option('modified').contains(True)

    @property
    def name(self):
        return self._internal_buffer.name

    @property
    def content(self):
        return List.wrap(self.target[:]).map(decode)

    def set_content(self, text):
        self.target[:] = text

    def nmap(self, keyseq, dispatch):
        return self.cmd('nmap <buffer><silent> {} {}'.format(keyseq, dispatch))

    def set_modifiable(self, value):
        self.set_optionb('modifiable', value)


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

    @property
    def cursor(self):
        return List.wrap(self.target.cursor)


class Tab(HasWindows):

    @property
    def _internal_window(self):
        return self.target.window

    def close(self):
        self.cmd('tabclose')


class NvimFacade(HasTabs, HasWindows, HasBuffers, HasTab):

    def __init__(self, vim: neovim.Nvim, prefix: str) -> None:
        super().__init__(vim, vim, prefix)

    def runtime(self, path: str, verbose=True):
        return self.cmd('runtime! {}.vim'.format(path), verbose=verbose)

    def echo(self, text: str):
        self.vcmd(echo(text, 'echo', prefix=Empty()))

    def echom(self, text: str):
        self.vcmd(echo(text, prefix=Just(self.prefix)))

    def echohl(self, hl: str, text: str):
        self.vcmd(echohl(text, hl, prefix=Just(self.prefix)))

    def echowarn(self, text: str):
        self.echohl('WarningMsg', text)

    def echoerr(self, text: str):
        self.echohl('ErrorMsg', text)

    def multi_line_info(self, text: List[str]):
        ''' as a workaround for possible bug in embedded nvim,
        only write in bulk when in production
        '''
        if amino.integration_test:
            text.foreach(self.log.info)
        else:
            self.log.info('\n'.join(text))

    def doautocmd(self, name, pat=''):
        c = 'doautocmd <nomodeline> {} {}'.format(name, pat)
        self.cmd(c)

    def uautocmd(self, name):
        self.doautocmd('User', name)

    def pautocmd(self, name):
        self.uautocmd('{}{}'.format(camelcaseify(self.prefix), name))

    def call(self, name, *a, **kw):
        return (
            Maybe.from_call(self.vim.call, name, *a, exc=NvimError, **kw)
            .to_either(lambda: 'vim call failed: {}'.format(
                format_funcall(name, a, kw)))
        )

    def eval(self, expr):
        return self.vim.eval(expr)

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
        self.tab.windows.foreach(__.reload())

    def cursor(self, line, col):
        return self.call('cursor', line, col)

    def feedkeys(self, keyseq, *a, **kw):
        self.vim.feedkeys(keyseq, *a, **kw)

B = TypeVar('B')


class NvimIO(Generic[A]):

    def __init__(self, apply: Callable[[NvimComponent], A]) -> None:
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

    def __init__(self, target, name):
        self._target = target
        self.name = name

    def __call__(self, *a, **kw):
        return self._target.async(lambda v: getattr(v, self.name)(*a, **kw))


class AsyncVimProxy(object):
    allow_async_relay = True

    def __init__(self, target):
        self._target = target
        self._target_tpe = type(target)

    @property
    def _need_relay(self):
        return (self.allow_async_relay and
                threading.current_thread() != threading.main_thread())

    def __getattr__(self, name):
        if self._need_relay:
            return self.async_relay(name)
        else:
            return getattr(self._target, name)

    def async_relay(self, name):
        if (hasattr(self._target_tpe, name)):
            attr = getattr(self._target_tpe, name)
            if isinstance(attr, FunctionType):
                return AsyncVimCallProxy(self._target, name)
            else:
                return self._async_attr(name)
        elif hasattr(self._target, name):
            return self._async_attr(name)
        else:
            return getattr(self._target, name)

    def _async_attr(self, name):
        return self._target.async(lambda v: getattr(v, name))

    def __eq__(self, other):
        return self.__getattr__('__eq__')(other)

    def __str__(self):
        return '{}({})'.format(self.__class__.__name__, str(self._target))


class ScratchBuilder(PRecord):
    params = dfield(Map())

    @property
    def tab(self):
        return self.copy(tab=True)

    def copy(self, **kw):
        return ScratchBuilder(self.params ** kw)

    @property
    def build(self):
        return (
            NvimIO(self._setup_tab) /
            self._setup_buffer /
            self._create
        )

    def _setup_tab(self, vim):
        tab = vim.tabnew()
        tab.window.set_optionb('wrap', False)
        return tab

    def _setup_buffer(self, tab):
        buffer = tab.bufnew()
        buffer.set_options('buftype', 'nofile')
        buffer.set_options('bufhidden', 'wipe')
        buffer.set_optionb('buflisted', False)
        buffer.set_optionb('swapfile', False)
        buffer.set_modifiable(False)
        return (tab, buffer)

    def _create(self, args):
        tab, buffer = args
        return ScratchBuffer(tab.vim, tab, buffer)


class ScratchBuffer(HasTab):

    def __init__(self, vim, tab, buffer):
        super().__init__(vim, buffer.target, buffer.prefix)
        self._tab = tab
        self._buffer = buffer

    @property
    def _internal_tab(self):
        return self._tab.target

    @property
    def _internal_buffer(self):
        return self._buffer.target

    def set_content(self, text):
        self._buffer.set_modifiable(True)
        self._buffer.set_content(text)
        self._buffer.set_modifiable(False)


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


class Syntax(Logging):

    def __init__(self, target):
        self.target = target

    def match(self, group, pat, *a, **kw):
        return self.cmd('match', group, pat, *a, **kw)

    def cmd(self, cmdname, group, pat, *a, **kw):
        opts = List.wrap(a) + Map(kw).to_list.smap('{}={}'.format)
        c = 'syntax {} {} /{}/ {}'.format(cmdname, group, pat, ' '.join(opts))
        self.target.cmd(c)

    def link(self, group, to):
        c = 'highlight link {} {}'.format(group, to)
        self.target.cmd(c)

__all__ = ('NvimFacade', 'HasNvim')
