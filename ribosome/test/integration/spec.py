import os
import abc
import pty
import json
import time
import asyncio
import subprocess
from functools import wraps
from threading import Thread
from datetime import datetime
from contextlib import contextmanager
from typing import Any, Callable, Generic, TypeVar, Type

import neovim
from neovim.api import Nvim

from amino import List, Either, Left, __, env, Path, Lists, _, Map
from amino.lazy import lazy
from amino.test import fixture_path, temp_dir, temp_file
from amino.test.path import base_dir, pkg_dir
from amino.test.spec import IntegrationSpecBase as AminoIntegrationSpecBase, default_timeout
from amino.util.string import camelcase
from amino.json import dump_json

import ribosome
from ribosome.logging import Logging
from ribosome import NvimFacade, NvimPlugin
from ribosome.nvim import AsyncVimProxy
from ribosome.test.fixtures import rplugin_template
from ribosome.request.rpc import rpc_handlers, RpcHandlerSpec
from ribosome.trans.message_base import Message
from ribosome.record import decode_json_compat, JsonError, encode_json_compat, decode_json
from ribosome.config import PluginSettings

A = TypeVar('A', bound=NvimPlugin)


def wait_for(cond: Callable[[], bool], timeout: float=None, intval: float=0.1) -> bool:
    to = default_timeout if timeout is None else timeout
    start = datetime.now()
    while (not cond() and (datetime.now() - start).total_seconds() < to):
        time.sleep(intval)
    return cond()


class IntegrationSpecBase(AminoIntegrationSpecBase):

    def setup(self) -> None:
        AminoIntegrationSpecBase.setup(self)
        AsyncVimProxy.allow_async_relay = False

    def teardown(self) -> None:
        AminoIntegrationSpecBase.teardown(self)


class VimIntegrationSpecI(abc.ABC):

    @abc.abstractproperty
    def _log_out(self) -> List[str]:
        ...


class VimIntegrationSpec(VimIntegrationSpecI, IntegrationSpecBase, Logging):

    def __init__(self) -> None:
        IntegrationSpecBase.__init__(self)
        self.tmux_nvim = 'RIBOSOME_TMUX_SPEC' in env
        self.tmux_nvim_external = False
        self.tmux_pane = None
        self.keep_tmux_pane = False
        self.vimlog = temp_dir('log') / 'vim'
        self.nvim_cmdline = List('nvim', '-V{}'.format(self.vimlog), '-n', '-u', 'NONE')
        self.log_format = '{levelname} {name}:{message}'
        self.subproc = None
        self.tmux_server = None

    def setup(self) -> None:
        IntegrationSpecBase.setup(self)
        env['RIBOSOME_SPEC'] = 1
        env['AMINO_DEVELOPMENT'] = 1
        env['RIBOSOME_PKG_DIR'] = str(pkg_dir())
        self._debug = 'RIBOSOME_DEVELOPMENT' in env
        self.logfile = temp_dir('log') / self.__class__.__name__
        self.logfile.touch()
        os.environ['RIBOSOME_LOG_FILE'] = str(self.logfile)
        os.environ['RIBOSOME_FILE_LOG_FMT'] = self.log_format
        self._pre_start_neovim()
        self.start_neovim()
        self._post_start_neovim()
        self._pre_start()
        self._start_plugin()
        self._post_start()

    def start_neovim(self) -> None:
        asyncio.get_child_watcher().attach_loop(asyncio.get_event_loop())
        if self.tmux_nvim:
            self.start_neovim_tmux_pane()
        elif self.tmux_nvim_external:
            self.start_neovim_tmux_bg()
        else:
            self.start_neovim_embedded()
        self.vim = self._nvim_facade(self.neovim)

    @property
    def python_path(self) -> str:
        global_path = env['PYTHONPATH'] | ''
        return '{}:{}'.format(self.project_path, global_path)

    @property
    def vim_proc_env(self) -> Map:
        return Map(
            NVIM_LISTEN_ADDRESS=self.nvim_socket,
            PYTHONPATH=self.python_path,
            RIBOSOME_LOG_FILE=self.logfile,
            RIBOSOME_FILE_LOG_FMT=f'\'{self.log_format}\'',
            AMINO_DEVELOPMENT='1',
        )

    def start_neovim_embedded(self) -> None:
        ''' start an embedded vim session that loads no init.vim.
        **self.vimlog** is set as log file. aside from being convenient, this is crucially necessary, as the first use
        of the session will block if stdout is used for output.
        '''
        argv = self.nvim_cmdline.cat('--embed')
        self.neovim = neovim.attach('child', argv=argv)

    @lazy
    def nvim_socket(self) -> str:
        return str(temp_dir('nvim_sockets') / List.random_string())

    @property
    def project_path(self) -> str:
        return str(base_dir().parent)

    @property
    def tmux_socket(self) -> str:
        return f'ribosome_{os.getpid()}'

    def connect_tmux(self, socket: str) -> Any:
        try:
            import libtmux
        except ImportError:
            raise Exception('install libtmux to run nvim in a tmux pane')
        else:
            return libtmux.Server(socket_name=socket)

    @property
    def tmux_window_external(self) -> Any:
        self.tmux_server = self.connect_tmux(self.tmux_socket)
        return self.tmux_server.sessions[0].windows[0]

    @property
    def tmux_window_local(self) -> Any:
        server = self.connect_tmux(None)
        session = next(s for s in server.sessions if int(s['session_attached']) >= 1)
        return session.attached_window

    @lazy
    def tmux_window(self) -> Any:
        return self.tmux_window_external if self.tmux_nvim_external else self.tmux_window_local

    def start_neovim_tmux_bg(self) -> None:
        conf = fixture_path('conf', 'tmux.conf')
        args = ['tmux', '-L', self.tmux_socket, '-f', str(conf)]
        master, slave = pty.openpty()
        self.subproc = subprocess.Popen(args, stdout=slave, stdin=slave, stderr=slave)
        self.start_neovim_tmux_pane()

    def start_neovim_tmux_pane(self) -> None:
        env_args = self.vim_proc_env.map2(lambda k, v: f'{k}={v}').cons('env')
        cmd = tuple(env_args + self.nvim_cmdline)
        out = self.tmux_window.cmd('split-window', '-d', '-P', '-F#{pane_id}', *cmd).stdout
        from libtmux import Pane
        self.tmux_pane = Pane(self.tmux_window, pane_id=out[0])
        self.neovim = neovim.attach('socket', path=self.nvim_socket)
        self.neovim.command('python3 sys.path.insert(0, \'{}\')'.format(self.python_path))

    def _cleanup_tmux(self) -> None:
        if self.tmux_pane is not None and not self.keep_tmux_pane:
            self.tmux_pane.cmd('kill-pane')

    def _nvim_facade(self, vim: Nvim) -> NvimFacade:
        return NvimFacade(vim, self._prefix)

    @abc.abstractproperty
    def _prefix(self) -> str:
        ...

    @abc.abstractmethod
    def plugin_name(self) -> str:
        ...

    def teardown(self) -> None:
        IntegrationSpecBase.teardown(self)
        if self._debug:
            self._log_out.foreach(self.log.info)
        if self.tmux_nvim:
            self._cleanup_tmux()
        if self.subproc is not None:
            self.subproc.kill()
        if self.tmux_server is not None:
            self.tmux_server.kill_server()

    def _pre_start_neovim(self) -> None:
        pass

    def _post_start_neovim(self) -> None:
        rtp = fixture_path('config', 'rtp')
        self.vim.options.amend_l('runtimepath', rtp)
        self.vim.vars.set_p('debug', True)

    def _pre_start(self) -> None:
        pass

    def _start_plugin(self) -> None:
        pass

    def _post_start(self) -> None:
        pass

    @property
    def _log_out(self) -> List[str]:
        return List.wrap(self.logfile.read_text().splitlines())

    def _cmd(self, cmd: str, args: List[str]) -> str:
        return args.cons(cmd).join_tokens

    def _json_cmd(self, cmd: str, args: List[str], data: dict) -> str:
        j = json.dumps(data).replace('"', '\\"')
        return f'{cmd} {args.join_tokens} {j}'

    def _run_cmd(self, f: Callable[..., Either[Exception, str]], cmd: str) -> Either[Exception, str]:
        try:
            return f(cmd)
        finally:
            self._wait(.1)

    def cmd(self, cmd: str, *args: str) -> Either[Exception, str]:
        return self._run_cmd(self.vim.cmd, self._cmd(cmd, Lists.wrap(args)))

    def cmd_sync(self, cmd: str, *args: str) -> Either[Exception, str]:
        return self._run_cmd(self.vim.cmd_sync, self._cmd(cmd, Lists.wrap(args)))

    def json_cmd(self, cmd: str, *args: str, **data: str) -> Either[Exception, str]:
        return self.cmd(self._json_cmd(cmd, Lists.wrap(args), data))

    def json_cmd_sync(self, cmd: str, *args: str, **data: str) -> Either[Exception, str]:
        return self.cmd_sync(self._json_cmd(cmd, Lists.wrap(args), data))

    @property
    def content(self) -> List[str]:
        return self.vim.buffer.content

    def message_log(self) -> Either[str, List[Message]]:
        return self.vim.call(f'{self.plugin_name}MessageLog') / Lists.wrap // __.traverse(decode_json_compat, Either)

    @property
    def state(self) -> Any:
        def error(err: JsonError) -> None:
            self.log.error(f'{err.desc}: {err.data}')
            raise err.error
        return self.vim.call(f'{self.plugin_prefix}State').flat_map(decode_json).value_or(error)

    @abc.abstractproperty
    def plugin_prefix(self) -> str:
        ...


def main_looped(fun):
    @wraps(fun)
    def wrapper(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        asyncio.get_child_watcher().attach_loop(loop)
        done = asyncio.Future(loop=loop)
        exc = None
        ret = None
        def runner():
            nonlocal ret
            local_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(local_loop)
            try:
                ret = fun(self)
            except Exception as e:
                nonlocal exc
                exc = e
            finally:
                loop.call_soon_threadsafe(lambda: done.set_result(True))
                local_loop.close()
        Thread(target=runner).start()
        loop.run_until_complete(done)
        loop.close()
        if exc is not None:
            raise exc
        return ret
    return wrapper


@contextmanager
def _nop_main_loop(self):
    yield


def _mock_async(self, f):
    ret = f(self)
    return ret


def _mock_proxy(self):
    return self


class ExternalIntegrationSpec(VimIntegrationSpec):

    def __init__(self) -> None:
        VimIntegrationSpec.__init__(self)
        self._report_expensive = False

    def _pre_start_neovim(self):
        super()._pre_start_neovim()
        ribosome.in_vim = False
        NvimFacade.async = _mock_async
        NvimFacade.main_event_loop = _nop_main_loop
        NvimFacade.proxy = property(_mock_proxy)
        NvimFacade.clean = lambda self: True
        AsyncVimProxy.allow_async_relay = False

    def _post_start_neovim(self):
        cls = self.plugin_class.get_or_raise()
        self.plugin = cls(self.neovim)

    def _await(self):
        if self.root is not None:
            self.root.await_state()

    @property
    def root(self):
        return self.plugin.state()

    def teardown(self):
        VimIntegrationSpec.teardown(self)
        if self.root is not None:
            self.root.stop(shutdown=False)
            if self._debug and self._report_expensive:
                self._report()

    def _report(self):
        self.root.sub.cat(self.root) % __.report()


class PluginIntegrationSpec(Generic[A], VimIntegrationSpec):

    def setup(self) -> None:
        self.log_format = '{message}'
        super().setup()

    @property
    def autostart_plugin(self) -> bool:
        return True

    def _post_start_neovim(self) -> None:
        super()._post_start_neovim()
        if self.autostart_plugin:
            self._setup_handlers()

    def _setup_handlers(self) -> None:
        rp_path = self.rplugin_path.get_or_raise()
        rp_handlers = self.handlers(rp_path).get_or_raise()
        self.vim.call(
            'remote#host#RegisterPlugin',
            'python3',
            str(rp_path),
            rp_handlers / _.encode,
        )

    @property
    def plugin_class(self) -> Either[str, Type[A]]:
        name = self.__class__.__name__
        e = 'property {}.plugin_class must return amino.Right(YourPluginClass)'
        return Left(e.format(name))

    @property
    def plugin_name(self) -> str:
        return camelcase(self.plugin_class.get_or_raise().name)

    @property
    def plugin_prefix(self) -> str:
        return camelcase(self.plugin_class.get_or_raise().prefix)

    @property
    def rplugin_path(self) -> Either[str, Path]:
        return self.plugin_class / self._auto_rplugin

    def handlers(self, rp_path: Path) -> Either[str, List[dict]]:
        return Either.import_from_file(rp_path, 'SpecPlugin') / self._auto_handlers

    def _auto_handlers(self, cls) -> List[RpcHandlerSpec]:
        return rpc_handlers(cls)

    def _auto_rplugin(self, cls):
        mod = cls.__module__
        name = cls.__name__
        rp_path = temp_file('ribosome', 'spec', 'spec_plugin.py')
        rp_path.write_text(rplugin_template.format(plugin_module=mod, plugin_class=name))
        return rp_path


Settings = TypeVar('Settings', bound=PluginSettings)
D = TypeVar('D')
M = TypeVar('M', bound=Message)


class AutoPluginIntegrationSpec(Generic[Settings, D], VimIntegrationSpec):

    def setup(self) -> None:
        self.log_format = '{message}'
        super().setup()

    @abc.abstractmethod
    def module(self) -> str:
        ...

    @property
    def _prefix(self) -> str:
        return self.plugin_prefix

    @property
    def plugin_name(self) -> str:
        return camelcase(self._prefix)

    @property
    def autostart_plugin(self) -> bool:
        return True

    def _post_start_neovim(self) -> None:
        super()._post_start_neovim()
        if self.autostart_plugin:
            self._setup_handlers()

    def _setup_handlers(self) -> None:
        stderr_handler_name = 'RibosomeJobStderr'
        stderr_handler_body = '''echo 'error starting rpc job on channel ' . a:id . ': ' . string(a:data)'''
        self.vim.define_function(stderr_handler_name, List('id', 'data', 'event'), stderr_handler_body)
        cmd = f'from ribosome.host import start_module; start_module({self.module()!r})'
        (
            self.vim
            .call('jobstart', ['python3', '-c', cmd], dict(rpc=True, on_stderr=stderr_handler_name))
            .get_or_raise()
        )

    def send_json(self, data: str) -> None:
        self.vim.call(f'{self.plugin_name}Send', data)

    def send(self, msg: M) -> None:
        self.send_json(dump_json(msg).o(encode_json_compat(msg)).get_or_raise())


__all__ = ('VimIntegrationSpec', 'ExternalIntegrationSpec', 'PluginIntegrationSpec')
