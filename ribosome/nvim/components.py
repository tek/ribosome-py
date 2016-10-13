import re
from typing import TypeVar, Callable, Any
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

from amino.util.string import camelcaseify

import amino
from amino import Maybe, may, List, Map, Boolean, Empty, Just, __, _, Try
from amino.util.string import decode
from amino.anon import format_funcall
from amino.lazy import lazy

import ribosome
from ribosome.logging import Logging
from ribosome.request.base import parse_int


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


def on_main_thread():
    return threading.current_thread() != threading.main_thread()


shutdown = False


class NvimComponent(Logging):

    def __init__(self, vim, target, prefix: str) -> None:
        if ribosome.in_vim and isinstance(target, (AsyncVimProxy,
                                                   NvimComponent)):
            msg = '{} created with non-native target {}'
            raise Exception(msg.format(self, target))
        self.vim = vim
        self.target = target
        self.prefix = prefix
        self._vars = Vars(self)
        self._options = Options(self)

    def __repr__(self):
        if on_main_thread():
            n = ''
        else:
            n = self._details
        return '{}({})'.format(self.__class__.__name__, n)

    @property
    def vars(self):
        return AsyncVimProxy(self._vars, self)

    @property
    def options(self):
        return AsyncVimProxy(self._options, self)

    @property
    def _details(self):
        return ''

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
        if not shutdown:
            result = futures.Future()  # type: futures.Future
            cb = lambda: result.set_result(f(self))
            self._run_on_main_thread(cb)
            return result.result()
        else:
            return f(self)

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
        return AsyncVimProxy(self, self)

    def prefixed(self, name: str):
        return '{}_{}'.format(self.prefix, name) if self.prefix else name

    def clean(self):
        self.vars.clean()

    def cmd(self, line: str, verbose=False, sync=False):
        ''' Wrap **Nvim.command**, default to async.
        **verbose** prevents the use of **silent**, which is used by
        default because headless nvim will deadlock if a command's
        output requires user input to proceed (e.g. multiline output)
        '''
        l = line if verbose else 'silent {}'.format(line)
        result = Try(self.vim.command, l, async=not sync)
        self._cmd_result(line, result, sync)
        return result

    def cmd_sync(self, line: str, verbose=False):
        return self.cmd(line, verbose=verbose, sync=True)

    def cmd_output(self, line: str) -> List[str]:
        return List.wrap(
            self.vim.command_output('silent {}'.format(line)).splitlines())

    def _cmd_result(self, line, result, sync: bool):
        if sync:
            self.log.debug('result of cmd \'{}\': {}'.format(line, result))
        else:
            self.log.debug('async cmd \'{}\''.format(line))

    def vcmd(self, line: str, sync=False):
        return self.cmd(line, verbose=True, sync=sync)

    @property
    def syntax(self):
        return Syntax(self)

    @lazy
    def root(self):
        return NvimFacade(self.vim, self.prefix)


class NvimCmd:

    def __init__(self, vim: NvimComponent, name: str, args: str='',
                 range=Empty(), silent=True) -> None:
        self.vim = vim
        self.name = name
        self.args = args
        self.range = range
        self.silent = silent

    def _cmdline(self, silent=None):
        sil = self.silent if silent is None else silent
        s = 'silent! ' if sil else ''
        r = self.range | ''
        return '{}{}{} {}'.format(s, r, self.name, self.args)

    def run_sync(self, silent=None):
        return self.vim.cmd_sync(self._cmdline(silent))

    def run_async(self, silent=None):
        return self.vim.cmd(self._cmdline(silent))

    def run_output(self, silent=None):
        return self.vim.cmd_output(self._cmdline(silent))


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

    def vsplit(self):
        self.cmd('vsplit')
        return self.window

    def new(self):
        self.cmd_sync('new')
        return self.window

    def vnew(self):
        self.cmd_sync('vnew')
        return self.window


class HasWindows(HasBuffers, HasWindow):

    @property
    def windows(self):
        return (
            self._internal_windows /
            (lambda a: Window(self.vim, a, self.prefix).proxy)
        )

    @property
    def _internal_windows(self):
        return List.wrap(self.vim.windows)

    def focus(self, number: int):
        return NvimCmd(self, 'wincmd', 'w', range=Just(number))


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
    def _details(self):
        return Try(lambda: self.desc) | ''

    @property
    def _internal_buffer(self):
        return self.target

    @property
    def _internal_window(self):
        return self.window.target

    @property
    def modified(self):
        return self.options('modified').contains(True)

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
        self.options.set_b('modifiable', value)

    @property
    def modifiable(self):
        return self.options.b('modifiable')

    @property
    def desc(self):
        n = self.name
        name = ' {}'.format(n) if n else ''
        return 'buf #{}{}'.format(self._internal_buffer.number, name)

    def autocmd(self, name, cmd):
        return NvimCmd(self, 'autocmd', '{} <buffer> {}'.format(name, cmd))

    def pvar_or_global(self, name):
        return self.vars.p(name).or_else(lambda: self.root.vars.p(name))


class Window(HasTab, HasBuffers):

    @property
    def _details(self):
        return Try(lambda: self.buffer.desc) | ''

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

    @property
    def line(self):
        return self.cursor.head

    def close(self):
        self.cmd('close')

    def close_unless_last(self):
        if self.tab.windows.length > 1:
            self.close()

    def set_cursor(self, line, col=0):
        self.target.cursor = (line, col)

    @property
    def width(self):
        return parse_int(self.target.width)

    @property
    def height(self):
        return parse_int(self.target.height)

    @property
    def size(self):
        return self.width & self.height


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

    def autocmd(self, name, pattern, cmd):
        return NvimCmd(self, 'autocmd', '{} {} {}'.format(name, pattern, cmd))

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

    def edit(self, path):
        if self.buffer.modifiable:
            self.write()
        return NvimCmd(self, 'edit!', str(path))

    def write(self):
        return NvimCmd(self, 'write!')

    @property
    def messages(self):
        return self.cmd_output('messages')


class AsyncVimCallProxy():

    def __init__(self, target, vim, name):
        self._target = target
        self._vim = vim
        self.name = name

    def __call__(self, *a, **kw):
        return self._vim.async(
            lambda v: getattr(self._target, self.name)(*a, **kw))

    def __repr__(self):
        return '{}({}, {})'.format(self.__class__.__name__, self.name,
                                   self._target)


class AsyncVimProxy():
    allow_async_relay = True

    def __init__(self, target, vim):
        self._vim = vim
        self._target = target
        self._target_tpe = type(target)

    @property
    def _need_relay(self):
        return self.allow_async_relay and on_main_thread()

    def __getattr__(self, name):
        if self._need_relay:
            return self.async_relay(name)
        else:
            return getattr(self._target, name)

    def async_relay(self, name):
        if (hasattr(self._target_tpe, name)):
            attr = getattr(self._target_tpe, name)
            if isinstance(attr, FunctionType):
                return AsyncVimCallProxy(self._target, self._vim, name)
            else:
                return self._async_attr(name)
        elif hasattr(self._target, name):
            return self._async_attr(name)
        else:
            return getattr(self._target, name)

    def _async_attr(self, name):
        return self._vim.async(lambda v: getattr(self._target, name))

    def __eq__(self, other):
        return self.__getattr__('__eq__')(other)

    def __repr__(self):
        return '{}({!r})'.format(self.__class__.__name__, self._target)

    def __call__(self, *a, **kw):
        return self.__getattr__('__call__')(*a, **kw)


class OptVar(Logging, metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def _get(self, name) -> Maybe[str]:
        ...

    @property
    def _desc(self):
        ...

    @may
    def __call__(self, name) -> Maybe[str]:
        v = self._get(name)
        if v is None:
            self.log.debug('{} not found: {}'.format(self._desc, name))
        return decode(v)

    def set(self, name, value):
        self.log.debug('setting {} {} to \'{}\''.format(self._desc, name,
                                                        value))
        try:
            self._set(name, value)
        except:
            msg = 'setting vim {} {} to {}'
            self.log.exception(msg.format(self._desc, name, value))

    def path(self, name: str) -> Maybe[Path]:
        return self(name).map(lambda a: Path(a).expanduser())  # type: ignore

    def dir(self, name: str) -> Maybe[Path]:
        var = self.path(name)
        val = var.filter(__.is_dir())
        if not val.is_just:
            msg = 'g:{} is not a directory ({})'
            self.log.error(msg.format(name, var))
        return val

    def typed(self, tpe: type, value: Maybe[A]) -> Maybe[A]:
        @may
        def check(v: A):
            if isinstance(v, tpe):
                return v
            else:
                msg = 'invalid type {} for {} {} (wanted {})'.format(
                    type(v), self._desc, v, tpe)
                self.log.error(msg)
        return value.flat_map(check)

    def s(self, name):
        return self.typed(str, self(name))

    def l(self, name):
        return self.typed(list, self(name))

    def d(self, name):
        return self.typed(dict, self(name))

    def b(self, name: str):
        return self.typed(bool, self(name)) / Boolean

    def i(self, name: str):
        return self.typed(int, self(name))


# FIXME recording variable name for eventual cleanup only works with a global
# NvimFacade instance
class Vars(OptVar):

    def __init__(self, vim) -> None:
        self.vim = vim
        self._vars = set()  # type: set

    def __repr__(self):
        return '{}({!r})'.format(self.__class__.__name__, self.vim)

    @property
    def internal(self):
        return self.vim.target.vars

    def _get(self, name):
        return self.internal.get(name)

    @property
    def _desc(self):
        return 'variable'

    def prefixed(self, name):
        return self.vim.prefixed(name)

    def _set(self, name, value):
        self.internal[name] = value
        self._vars.add(name)

    def clean(self):
        for name in self._vars:
            if not re.match('^[A-Z].*', name):
                del self.internal[name]
        self._vars = set()

    def p(self, name) -> Maybe[str]:
        return self(self.prefixed(name))

    def set_p(self, name, value):
        self.set(self.prefixed(name), value)

    def ppath(self, name: str) -> Maybe[Path]:
        return self.path(self.prefixed(name))

    def ppathl(self, name: str) -> Maybe[Path]:
        return self.pl(name)\
            .map(lambda l: l.map(Path).map(__.expanduser()))

    def pdir(self, name: str) -> Maybe[Path]:
        return self.dir(self.prefixed(name))

    def ps(self, name):
        return self.typed(str, self.vars.p(name))

    def pl(self, name):
        return self.typed(list, self.p(name))

    def pd(self, name):
        return self.typed(dict, self.p(name))

    def pb(self, name: str):
        return self.typed(bool, self.p(name)) / Boolean

    def pi(self, name: str):
        return self.typed(int, self.p(name))

    @property
    def all(self):
        rex = re.compile('^#(?P<num>\d+)$')
        def parse(k, v):
            v2 = (Maybe(rex.match(v)) / __.groupdict() / Map //
                  __.get('num') // parse_int)
            return k, (v2 | v)
        lines = (
            (self.vim.cmd_output('silent let') / __.split(maxsplit=1) /
                List.wrap)
            .filter(_.length == 2)
            .filter_not(lambda a: a[0].startswith('v:'))
            .map2(parse)
        )
        return Map(lines)


class Options(OptVar):

    def __init__(self, vim) -> None:
        self.vim = vim

    def _get(self, name):
        return self.vim.target.options.get(name)

    @property
    def _desc(self):
        return 'option'

    def _set(self, name: str, value):
        self.vim.target.options[name] = value

    def s(self, name: str):
        return self.typed(str, self(name))

    def set_s(self, name: str, value):
        return self.set(name, str(value))

    def l(self, name: str) -> List[str]:
        return self.s(name)\
            .map(lambda a: a.split(','))\
            .map(List.wrap)\
            .get_or_else(List())

    def amend_l(self, name: str, value):
        if not isinstance(value, list):
            value = List(value)
        new_value = (self.l(name) + list(map(str, value))).distinct
        self.set_l(name, new_value)

    def set_l(self, name: str, value: List[str]):
        self.vim.target.options[name] = ','.join(value)

    def b(self, name: str):
        return self.typed(bool, self(name))

    def set_b(self, name: str, value):
        return self.set(name, bool(value))

    def typed(self, tpe: type, value: Maybe[A]) -> Maybe[A]:
        @may
        def check(v: A):
            if isinstance(v, tpe):
                return v
            else:
                msg = 'invalid type {} for option {} (wanted {})'.format(
                    type(v), v, tpe)
                self.log.error(msg)
        return value.flat_map(check)


class Flags:

    def __init__(self, vars, prefix: bool) -> None:
        self.vars = vars
        self.prefix = prefix

    def get(self, name, default=False):
        v = (self.vars.p(name) if self.prefix else self.vars(name))\
            .get_or_else(default)
        return Boolean(v)

    def __getattr__(self, name):
        return self.get(name)


class HasNvim:

    def __init__(self, vim: NvimFacade) -> None:
        self.vim = vim
        self.flags = Flags(vim.vars, False)
        self.pflags = Flags(vim.vars, True)


class Syntax(Logging):

    def __init__(self, target):
        self.target = target

    def _opts(self, *a, **kw):
        o = List.wrap(a) + Map(kw).to_list.map2('{}={}'.format)
        return ' '.join(o)

    def match(self, group, pat, *a, **kw):
        return self.cmd('match', group, pat, *a, **kw)

    def cmd(self, cmdname, group, pat, *a, **kw):
        c = 'syntax {} {} /{}/ {}'.format(cmdname, group, pat,
                                          self._opts(*a, **kw))
        self.target.cmd(c)

    def link(self, group, to):
        c = 'highlight link {} {}'.format(group, to)
        self.target.cmd(c)

    def highlight(self, group, *a, **kw):
        c = 'highlight {} {}'.format(group, self._opts(*a, **kw))
        self.target.cmd(c)

__all__ = ('NvimFacade', 'HasNvim')
