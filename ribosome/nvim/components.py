import re
import typing
from typing import TypeVar, Callable, Any, Union, Optional, Generic, Type
from pathlib import Path
import threading
from concurrent import futures
from contextlib import contextmanager
import asyncio
import abc
from types import FunctionType
import inspect
import traceback
import time
import functools

import neovim
from neovim.api import NvimError, Nvim
from neovim.api.common import Remote

from msgpack import ExtType

from amino.util.string import camelcaseify

import amino
from amino import Maybe, List, Map, Boolean, Empty, Just, __, _, Try, Either, Left, Right, L, Lists
from amino.util.string import decode
from amino.util.fun import format_funcall
from amino.lazy import lazy
from amino.io import IOException
from amino.util.numeric import parse_int
from amino.dat import Dat
from amino.dispatch import dispatch_with

import ribosome
from ribosome.logging import Logging


def squote(text: str) -> str:
    return text.replace("'", "''")


def dquote(text: str) -> str:
    return text.replace('"', '\\"')


def quote(text: str) -> str:
    return dquote(squote(text))


A = TypeVar('A')


def echo(text: Union[str, List[str]], cmd: str='echom', prefix: Maybe[str]=Empty()) -> List[str]:
    lines = text if isinstance(text, List) else Lists.lines(str(text))
    pre = prefix.map(_ + ': ') | ''
    return lines.map(lambda a: '{} "{}{}"'.format(cmd, pre, dquote(a)))


def echohl(text: Union[str, List[str]], hl: str, prefix: Maybe[str]=Empty()) -> List[str]:
    return echo(text, prefix=prefix).cons(f'echohl {hl}').cat('echohl None')


def not_on_main_thread() -> bool:
    return threading.current_thread() != threading.main_thread()


shutdown = False

R = TypeVar('R', bound=Remote)


class NvimComponent(Generic[R], Logging):

    def __init__(self, vim: Nvim, target: Union['NvimComponent', 'AsyncVimProxy', R], prefix: str) -> None:
        self.vim = vim
        self.target = target
        self.prefix = prefix
        if ribosome.in_vim and isinstance(target, (AsyncVimProxy, NvimComponent)):
            msg = '{} created with non-native target {}'
            raise Exception(msg.format(self, target))
        self._vars = Vars(self)
        self._options = Options(self)

    def __repr__(self) -> str:
        n = '' if not_on_main_thread() else self._details
        return '{}({}, {})'.format(self.__class__.__name__, self.prefix, n)

    @property
    def vars(self) -> 'AsyncVimProxy[Vars]':
        return AsyncVimProxy(self._vars, self)

    @property
    def options(self) -> 'AsyncVimProxy[Options]':
        return AsyncVimProxy(self._options, self)

    @property
    def _details(self) -> str:
        return ''

    @property
    def loop(self) -> Any:
        return self.vim._session._async_session._msgpack_stream._event_loop._loop

    def delay(self, f: Callable[[], None], timeout: float) -> None:
        cb = lambda: self._run_on_main_thread(f)
        threading.Timer(1.0, cb).start()

    def async_call(self, f: Callable[..., Any], *a: Any, **kw: Any) -> Any:
        ''' run a callback function on the main thread and return its
        value (blocking). the callback receives 'self' as an argument.
        '''
        if not shutdown:
            msg = 'running {} on main thread blocking'
            self.log.debug2(lambda: msg.format(format_funcall(f.__name__, a, kw)))
            result_fut = futures.Future()  # type: futures.Future
            @functools.wraps(f)
            def cb() -> None:
                result_fut.set_result(f(self, *a, **kw))
            self._run_on_main_thread(cb)
            result = result_fut.result()
            self.log.debug2(lambda: f'async returns {result}')
            return result
        else:
            return f(self, *a, **kw)

    async = async_call

    def _run_on_main_thread(self, f: Callable[..., Any], *a: Any, **kw: Any) -> None:
        ''' run a callback function on the host's main thread
        '''
        frame = inspect.currentframe()
        def dispatch() -> None:
            self.log.debug2(lambda: 'running on main thread: {}'.format(format_funcall(f.__name__, a, kw)))
            try:
                f(*a, **kw)
            except NvimError as e:
                self._report_nvim_error(e, frame)
            else:
                self.log.debug2('{} successful'.format(f.__name__))
        self.vim._session.threadsafe_call(dispatch)

    def _report_nvim_error(self, err: str, frame: traceback.FrameSummary) -> None:
        self.log.error('async vim call failed with \'{}\''.format(decode(err)))
        self.log.error(''.join(traceback.format_stack(frame)[:-5]))

    @contextmanager
    def main_event_loop(self):
        ''' run the asyncio main loop on vim's pyuv main thread and
        yield the loop to the with statement in the current thread.
        '''
        def get_event_loop(v) -> Any:
            return asyncio.get_event_loop()
        main = self.async_call(get_event_loop)
        fut = main.create_future()
        if not main.is_running():
            self._run_on_main_thread(main.run_until_complete, fut)
            start = time.time()
            while not main.is_running() and time.time() - start < 1:
                time.sleep(0.01)
            if not main.is_running():
                self.log.debug('timed out waiting for main loop to start')
        try:
            yield main
        except:
            self.log.exception('error while running callback in main loop:')
        main.call_soon_threadsafe(L(fut.set_result)(True))

    @contextmanager
    def threadsafe_subprocess(self):
        def set_watcher(vim: Any) -> None:
            try:
                asyncio.get_child_watcher().attach_loop(asyncio.get_event_loop())
            except Exception:
                pass
        self.async_call(set_watcher)
        with self.main_event_loop() as main:
            yield main

    @property
    def proxy(self):
        return AsyncVimProxy(self, self)

    def prefixed(self, name: str):
        return '{}_{}'.format(self.prefix, name) if self.prefix else name

    def clean(self):
        self.vars.clean()

    def _cmd(self, line: str, verbose=False, sync=False) -> Either[Exception, None]:
        l = line if verbose else 'silent {}'.format(line)
        return Try(self.vim.command, l, async=not sync)

    def cmd(self, line: str, verbose=False, sync=False, report=True) -> Either[Exception, None]:
        ''' Wrap **Nvim.command**, default to async.
        **verbose** prevents the use of **silent**, which is used by
        default because headless nvim will deadlock if a command's
        output requires user input to proceed (e.g. multiline output)
        '''
        return (
            self._cmd(line, verbose, sync)
            .bieffect(
                L(self._cmd_error)(line, _, sync, report),
                L(self._cmd_success)(line, _, sync)
            )
        )

    def cmd_sync(self, line: str, verbose=False, report=True) -> Either[Exception, None]:
        return self.cmd(line, verbose=verbose, sync=True, report=report)

    def cmd_output(self, line: str) -> List[str]:
        return Lists.wrap(self.vim.command_output('silent {}'.format(line)).splitlines())

    def _cmd_success(self, line: str, result, sync: bool) -> None:
        if sync:
            self.log.debug1(lambda: f'result of cmd \'{line}\': {result}')
        else:
            self.log.debug1('async cmd \'{}\''.format(line))

    def _cmd_error(self, line, exc, sync, report: bool) -> None:
        if not report:
            return
        err = exc.cause if isinstance(exc, IOException) else exc
        if amino.development:
            a = '' if sync else 'a'
            msg = f'running nvim {a}sync cmd `{line}`'
            if isinstance(err, Exception):
                self.log.caught_exception_error(msg, err)
            else:
                self.log.error(f'{msg}: {err}')
        else:
            self.log.error(decode(err))

    def vcmd(self, line: str, sync=False, report=True) -> Either[Exception, None]:
        return self.cmd(line, verbose=True, sync=sync, report=report)

    def normal(self, keys) -> Either[Exception, None]:
        return self.cmd_sync('normal! {}'.format(keys))

    @property
    def syntax(self) -> 'Syntax':
        return Syntax(self)

    @lazy
    def root(self) -> 'NvimFacade':
        return NvimFacade(self.vim, self.prefix)


class NvimCmd:

    def __init__(self, vim: NvimComponent, name: str, args: str='', range=Empty(), silent=True) -> None:
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

    @abc.abstractproperty
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

    @abc.abstractproperty
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

    @abc.abstractproperty
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

    def set_content(self, text, rng=slice(None)):
        self.target[rng] = text

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

    @property
    def id(self):
        return self._internal_buffer.number

    @property
    def line_count(self):
        return self.content.length

    @property
    def loaded(self) -> Boolean:
        return self.target.valid


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

    @property
    def line0(self):
        return self.line / (_ - 1)

    def close(self):
        self.cmd('close')

    def close_unless_last(self):
        if self.tab.windows.length > 1:
            self.close()

    def set_cursor(self, line, col=0):
        buf_max = self.buffer.content.length
        self.target.cursor = (min(line, buf_max), col)

    @property
    def width(self):
        return parse_int(self.target.width)

    @property
    def height(self):
        return parse_int(self.target.height)

    @property
    def size(self):
        return self.width & self.height

    def visual_line(self, start, end):
        self.set_cursor(start)
        self.normal('V')
        self.set_cursor(end)


class Tab(HasWindows):

    @property
    def _internal_window(self):
        return self.target.window

    def close(self):
        self.cmd('tabclose')


class CallError(Dat['CallError']):

    def __init__(self, msg: str, header: str, error: Union[Exception, str], funcall: str) -> None:
        self.msg = msg
        self.header = header
        self.error = error
        self.funcall = funcall


class NvimFacade(HasTabs, HasWindows, HasBuffers, HasTab):

    @staticmethod
    def stdio_with_logging(name: str) -> 'NvimFacade':
        from ribosome.logging import nvim_logging
        native = neovim.attach('stdio')
        vim = NvimFacade(native, name)
        nvim_logging(vim)
        return vim

    def __init__(self, vim: neovim.Nvim, prefix: str) -> None:
        super().__init__(vim, vim, prefix)

    @property
    def channel_id(self) -> int:
        return self.vim.channel_id

    @property
    def rpc_types(self) -> Map[str, type]:
        return self.vim.types

    def runtime(self, path: str, verbose=True):
        return self.cmd_sync('runtime! {}.vim'.format(path), verbose=verbose)

    def _echo(self, lines: List[str]) -> None:
        return lines.traverse(L(self._cmd)(_, True), Right)

    def echo(self, text: Union[str, List[str]]):
        self._echo(echo(text, 'echo', prefix=Just(self.prefix)))

    def echom(self, text: Union[str, List[str]]):
        self._echo(echo(text, prefix=Just(self.prefix)))

    def echohl(self, hl: Union[str, List[str]], text: Union[str, List[str]]):
        self._echo(echohl(text, hl, prefix=Just(self.prefix)))

    def echowarn(self, text: Union[str, List[str]]):
        self.echohl('WarningMsg', text)

    def echoerr(self, text: Union[str, List[str]]):
        self.echohl('ErrorMsg', text)

    def multi_line_info(self, text: List[str]):
        ''' as a workaround for possible bug in embedded nvim,
        only write in bulk when in production
        '''
        if amino.integration_test:
            text.foreach(self.log.info)
        else:
            self.log.info('\n'.join(text))

    def doautocmd(self, name, pat='') -> Either[Exception, None]:
        c = 'doautocmd <nomodeline> {} {}'.format(name, pat)
        return self.cmd(c)

    def uautocmd(self, name) -> Either[Exception, None]:
        return self.doautocmd('User', name)

    def pautocmd(self, name) -> Either[Exception, None]:
        return self.uautocmd('{}{}'.format(camelcaseify(self.prefix), name))

    def autocmd(self, name, pattern, cmd) -> NvimCmd:
        return NvimCmd(self, 'autocmd', '{} {} {}'.format(name, pattern, cmd))

    def _call(self, name: str, *args: Any, sync=True, **kw: Any) -> Either[Exception, A]:
        return Try(self.vim.call, name, *args, async=not sync, **kw)

    def call(self, name: str, *args: Any, sync=True, **kw: Any) -> Either[str, A]:
        return (
            self._call(name, *args, sync=sync, **kw)
            .lmap(L(self._call_error)(name, args, kw, _, sync))
            .leffect(self._log_call_error)
            .lmap(lambda a: f'vim call `{a.funcall}` failed: {a.msg}')
        )

    def _call_error(self, name: str, args: tuple, kw: dict, err: Exception, sync: bool) -> CallError:
        a = '' if sync else 'a'
        funcall = format_funcall(name, args, kw)
        header = f'calling {a}sync nvim function `{funcall}`'
        thread_error = str(err) == "'NoneType' object has no attribute 'switch'"
        undefined = not self.function_exists(name)
        msg = (
            'thread scheduling error'
            if isinstance(err, Exception) and thread_error else
            '''function doesn't exist'''
            if undefined else
            str(err)
        )
        return CallError(msg, header, err, funcall)

    def _log_call_error(self, error: CallError) -> None:
        if isinstance(error.error, Exception) and amino.development:
            self.log.caught_exception(error.header, error.error)
        self.log.error(f'{error.header}: {error.msg}')

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
    def messages(self) -> List[str]:
        return self.cmd_output('messages')

    @property
    def commands(self) -> List[str]:
        return self.cmd_output('command')

    @property
    def commands_s(self) -> str:
        return self.commands.join_lines

    def import_pvar_path(self, name: str) -> Maybe[A]:
        return self.buffer.vars.p(name).o(lambda: self.vars.p(name)).flat_map(Either.import_path)

    def function_exists(self, name: str) -> Boolean:
        return self._call('exists', f'*{name}').true

    def command_exists(self, name: str) -> Boolean:
        return self.call('exists', f':{name}').contains(2)

    def execute(self, code: Union[str, List[str]]) -> None:
        lines = code if isinstance(code, List) else Lists.lines(code)
        return self.call('execute', list(lines))

    def run_once_defined(self, job: Callable[[], Either[str, A]], err: Callable[[str], str], timeout: int=3
                         ) -> Either[str, A]:
        result: Either[str, A] = Left('not started yet')
        start = time.time()
        while not result.is_right and time.time() - start < timeout:
            time.sleep(.01)
            result = job()
        return result.lmap(err)

    def call_once_defined(self, name: str, *args: str, timeout: int=3, **kw: Any) -> Either[str, A]:
        return self.run_once_defined(L(self._call)(name, *args, **kw), lambda a: f'function {name} did not appear: {a}',
                                     timeout=timeout)

    def cmd_once_defined(self, name: str, *args: str, timeout: int=3, **kw: Any) -> Either[str, A]:
        return self.run_once_defined(
            L(self.cmd_sync)(name, *args, report=False, **kw),
            lambda a: f'cmd {name} did not appear: {a}',
            timeout=timeout
        )

    def wait_for_command(self, name: str, timeout: int=3) -> Either[str, None]:
        f = lambda: self.command_exists(name).e('', None)
        return self.run_once_defined(f, lambda a: 'cmd {name} did not appear', timeout=timeout)

    def define_function(self, name: str, params: List[str], body: str) -> None:
        self.cmd_sync(f'function! {name}({params.join_comma})\n{body}\nendfunction')

    def cd(self, dir: Path) -> None:
        return self.vim.chdir(str(dir))

    @property
    def cwd(self) -> Either[str, Path]:
        return self.call('getcwd') // L(Try)(Path, _)

    @property
    def flags(self) -> 'Flags':
        return Flags(self.vars, False)

    @property
    def pflags(self) -> 'Flags':
        return Flags(self.vars, True)

    def decode_vim_data(self, data: Any) -> Any:
        return decode(
            Boolean.isinstance(data, ExtType)
            .m(lambda: self.rpc_types.lift(data.code)) /
            (lambda A: A(self, (data.code, data.data))) |
            data
        )

    def encode_vim_data(self, data: Any) -> Any:
        return decode(data)


@decode.register(ExtType)
def decode_ext_type(data: Remote) -> Any:
    return ExtType(*data.code_data)


class AsyncVimCallProxy(Generic[A]):

    def __init__(self, target: A, vim: NvimComponent, name: str) -> None:
        self._target = target
        self._vim = vim
        self.name = name

    def __call__(self, *a: Any, **kw: Any) -> Any:
        def proxy_call(vim: NvimComponent, target: A, name: str, *a: Any, **kw: Any) -> Any:
            return getattr(target, name)(*a, **kw)
        return self._vim.async_call(proxy_call, self._target, self.name, *a, **kw)

    def __repr__(self) -> str:
        return '{}({}, {})'.format(self.__class__.__name__, self.name, self._target)


class AsyncVimProxy(Generic[A]):
    allow_async_relay = True

    def __init__(self, target: A, vim: NvimComponent) -> None:
        self._vim = vim
        self._target = target
        self._target_tpe = type(target)

    @property
    def _need_relay(self):
        return self.allow_async_relay and not_on_main_thread()

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

    def _async_attr(self, name: str) -> Any:
        def proxy_getattr(vim, target: NvimComponent, name: str) -> Any:
            return getattr(target, name)
        return self._vim.async_call(proxy_getattr, self._target, name)

    def __eq__(self, other):
        return self.__getattr__('__eq__')(other)

    def __repr__(self):
        return '{}({!r})'.format(self.__class__.__name__, self._target)

    def __call__(self, *a, **kw):
        return self.__getattr__('__call__')(*a, **kw)


class OptVar(Logging, abc.ABC):

    @abc.abstractmethod
    def _get(self, name: str) -> Optional[Any]:
        ...

    @abc.abstractmethod
    def _set(self, name: str, value: A) -> None:
        ...

    @property
    def _desc(self) -> str:
        ...

    def __call__(self, name: str) -> Either[str, Any]:
        v = self._get(name)
        if v is None:
            msg = '{} not found: {}'.format(self._desc, name)
            self.log.debug(msg)
            return Left(msg)
        else:
            return Right(decode(v))

    def set(self, name: str, value: A) -> None:
        self.log.debug('setting {} {} to \'{}\''.format(self._desc, name, value))
        try:
            self._set(name, value)
        except:
            msg = 'setting vim {} {} to {}'
            self.log.exception(msg.format(self._desc, name, value))

    def path(self, name: str) -> Either[str, Path]:
        return self(name).map(lambda a: Path(a).expanduser())

    def dir(self, name: str) -> Either[str, Path]:
        var = self.path(name)
        val = var.filter(__.is_dir())
        if not val.present:
            msg = 'g:{} is not a directory ({})'
            self.log.error(msg.format(name, var))
        return val

    def typed(self, tpe: Type[A], value: Either[str, Any]) -> Either[str, A]:
        def check(v: A) -> Either[str, A]:
            if isinstance(v, tpe):
                return Right(v)
            else:
                msg = f'invalid type {type(v)} for {self._desc} {v} (wanted {tpe})'
                self.log.error(msg)
                return Left(msg)
        return value.flat_map(check)

    def s(self, name: str) -> Either[str, str]:
        return self.typed(str, self(name))

    def l(self, name: str) -> Either[str, List]:
        return self.typed(list, self(name)) / Lists.wrap

    def d(self, name: str) -> Either[str, dict]:
        return self.typed(dict, self(name))

    def m(self, name: str) -> Either[str, Map]:
        return self.d(name) / Map

    def b(self, name: str) -> Either[str, Boolean]:
        return self.typed(bool, self(name)) / Boolean

    def i(self, name: str) -> Either[str, int]:
        return self.typed(int, self(name))

    def exists(self, name: str) -> Boolean:
        return self(name).is_right


# FIXME recording variable name for eventual cleanup only works with a global
# NvimFacade instance
class Vars(OptVar):

    def __init__(self, vim: NvimComponent) -> None:
        self.vim = vim
        self._vars: set = set()

    def __repr__(self) -> str:
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

    def p(self, name) -> Either[str, str]:
        return self(self.prefixed(name))

    def set_p(self, name, value):
        self.set(self.prefixed(name), value)

    def ppath(self, name: str) -> Either[str, Path]:
        return self.path(self.prefixed(name))

    def ppathl(self, name: str) -> Either[str, Path]:
        return self.pl(name)\
            .map(lambda l: l.map(Path).map(__.expanduser()))

    def pdir(self, name: str) -> Either[str, Path]:
        return self.dir(self.prefixed(name))

    def ps(self, name):
        return self.typed(str, self.vars.p(name))

    def pl(self, name):
        return self.typed(list, self.p(name))

    def pd(self, name):
        return self.typed(dict, self.p(name))

    def pm(self, name):
        return self.pd(name) / Map

    def pb(self, name: str) -> Either[str, Boolean]:
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

    def ensure(self, name: str, default: Any) -> None:
        if not self.exists(name):
            self.set(name, default)

    def ensure_p(self, name: str, default: Any) -> None:
        self.ensure(self.prefixed(name), default)


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
        c = 'syntax {} {} /{}/ {}'.format(cmdname, group, pat, self._opts(*a, **kw))
        self.target.cmd(c)

    def link(self, group, to):
        c = 'highlight link {} {}'.format(group, to)
        self.target.cmd(c)

    def highlight(self, group, *a, **kw):
        c = 'highlight {} {}'.format(group, self._opts(*a, **kw))
        self.target.cmd(c)

__all__ = ('NvimFacade', 'HasNvim')
