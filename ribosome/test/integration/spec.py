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
from typing import Any, Callable, Generic, TypeVar

import neovim
from neovim.api import Nvim

from amino import List, Either, __, env, Path, Lists, Map
from amino.lazy import lazy
from amino.test import fixture_path, temp_dir
from amino.test.path import base_dir, pkg_dir
from amino.test.spec import IntegrationSpecBase as AminoIntegrationSpecBase, default_timeout
from amino.util.string import camelcase
from amino.json import dump_json, decode_json
from amino.json.data import JsonError

import ribosome
from ribosome.logging import Logging
from ribosome.nvim import AsyncVimProxy, NvimFacade
from ribosome.trans.message_base import Message
from ribosome.config.settings import Settings


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
        self._debug = 'RIBOSOME_DEVELOPMENT' in env

    def setup(self) -> None:
        IntegrationSpecBase.setup(self)
        env['RIBOSOME_SPEC'] = 1
        env['AMINO_DEVELOPMENT'] = 1
        env['RIBOSOME_PKG_DIR'] = str(pkg_dir())
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
        wait_for(Path(self.nvim_socket).is_socket)
        from libtmux import Pane
        self.tmux_pane = Pane(self.tmux_window, pane_id=out[0])
        self.neovim = neovim.attach('socket', path=self.nvim_socket)
        self.neovim.command('python3 sys.path.insert(0, \'{}\')'.format(self.python_path))

    def _cleanup_tmux(self) -> None:
        if self.tmux_pane is not None and not self.keep_tmux_pane:
            self.tmux_pane.cmd('kill-pane')

    def _nvim_facade(self, vim: Nvim) -> NvimFacade:
        return NvimFacade(vim, self.plugin_name())

    @abc.abstractmethod
    def plugin_name(self) -> str:
        ...

    def plugin_short_name(self) -> str:
        return self.plugin_name()

    def full_cmd_prefix(self) -> str:
        return camelcase(self.plugin_name())

    def short_cmd_prefix(self) -> str:
        return camelcase(self.plugin_short_name())

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
        j = json.dumps(data)
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
        return self.vim.call(f'{self.full_cmd_prefix()}MessageLog') / Lists.wrap // __.traverse(decode_json, Either)

    def trans_log(self) -> Either[str, List[Message]]:
        return self.vim.call(f'{self.full_cmd_prefix()}TransLog') // decode_json

    @property
    def state(self) -> Any:
        def error(err: JsonError) -> None:
            self.log.error(f'{err.error}: {err.data}')
            raise err.exception
        response = self.vim.call(f'{self.full_cmd_prefix()}State').get_or_raise()
        return decode_json(response).value_or(error)


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


S = TypeVar('S', bound=Settings)
D = TypeVar('D')


class AutoPluginIntegrationSpec(Generic[S, D], VimIntegrationSpec):

    def setup(self) -> None:
        self.log_format = '{message}'
        del env['AMINO_COMPILE_COCO']
        super().setup()

    def module(self) -> str:
        return self.plugin_name()

    @property
    def autostart_plugin(self) -> bool:
        return True

    def _post_start_neovim(self) -> None:
        super()._post_start_neovim()
        if self.autostart_plugin:
            self.start_plugin()

    def start_plugin(self) -> None:
        stderr_handler_name = 'RibosomeSpecStderr'
        stderr_handler_body = '''
        let err = substitute(join(a:data, '\\r'), '"', '\\"', 'g')
        python3 import amino
        python3 from ribosome.logging import ribosome_envvar_file_logging
        python3 ribosome_envvar_file_logging()
        execute 'python3 amino.amino_log.error(f"""error starting rpc job on channel ' . a:id . ':\\r' . err . '""")'
        '''
        self.vim.define_function(stderr_handler_name, List('id', 'data', 'event'), stderr_handler_body)
        cmd = f'from ribosome.host import start_module; start_module({self.module()!r})'
        args = ['python3', '-c', cmd]
        opts = dict(rpc=True, on_stderr=stderr_handler_name)
        self.vim.call('jobstart', args, opts).get_or_raise()

    def send_json(self, data: str) -> None:
        self.vim.call(f'{self.plugin_name}Send', data)

    def send(self, msg: Message) -> None:
        self.send_json(dump_json(msg).get_or_raise())

    def _pre_start(self) -> None:
        if self.autostart_plugin:
            self.pvar_becomes('started', True)


__all__ = ('VimIntegrationSpec', 'ExternalIntegrationSpec', 'AutoPluginIntegrationSpec')
