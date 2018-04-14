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

from amino import List, Either, __, env, Path, Lists, Map, do, Do, Nil, _, Maybe, Just, Nothing
from amino.lazy import lazy
from amino.test import fixture_path, temp_dir
from amino.test.path import base_dir, pkg_dir
from amino.test.spec import IntegrationSpecBase as AminoIntegrationSpecBase, default_timeout
from amino.util.string import camelcase
from amino.json import decode_json
from amino.json.data import JsonError

import ribosome
from ribosome.logging import Logging
from ribosome.nvim.api.data import NvimApi
from ribosome.config.settings import Settings
from ribosome.nvim.api.data import NativeNvimApi
from ribosome.nvim.api.option import option_cat
from ribosome.nvim.api.variable import variable_set_prefixed
from ribosome.nvim.api.function import define_function, nvim_call_function
from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.command import nvim_command


def wait_for(cond: Callable[[], bool], timeout: float=None, intval: float=0.1) -> bool:
    to = default_timeout if timeout is None else timeout
    start = datetime.now()
    while (not cond() and (datetime.now() - start).total_seconds() < to):
        time.sleep(intval)
    return cond()


class IntegrationSpecBase(AminoIntegrationSpecBase):

    def setup(self) -> None:
        AminoIntegrationSpecBase.setup(self)

    def teardown(self) -> None:
        AminoIntegrationSpecBase.teardown(self)


class VimIntegrationSpecI(abc.ABC):

    @abc.abstractproperty
    def _log_out(self) -> List[str]:
        ...


def format_json_cmd(args: List[str], data: dict) -> str:
    j = json.dumps(data)
    return f'{args.join_tokens} {j}'


def json_cmd(cmd: str, *args: str, **data: str) -> NvimIO[str]:
    return nvim_command(cmd, format_json_cmd(Lists.wrap(args), data), verbose=True)


class VimIntegrationSpec(VimIntegrationSpecI, IntegrationSpecBase, Logging):

    def __init__(self) -> None:
        IntegrationSpecBase.__init__(self)
        self.tmux_nvim = 'RIBOSOME_TMUX_SPEC' in env
        self.tmux_nvim_external = False
        self.tmux_pane_id = None
        self.keep_tmux_pane = False
        self.vimlog = temp_dir('log') / 'vim'
        self.nvim_cmdline = List('nvim', '-V{}'.format(self.vimlog), '-n', '-u', 'NONE')
        self.log_format = '{levelname} {name}:{message}'
        self.subproc = None
        self.ribo_tmux = None
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
        self.vim = self.create_nvim_api(self.neovim)

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

    def connect_tmux(self, external: bool) -> Any:
        try:
            from chiasma.test.tmux_spec import tmux_spec_socket
            from chiasma.tmux import Tmux
        except ImportError:
            raise Exception('install chiasma to run nvim in a tmux pane')
        else:
            return Tmux.cons(socket=tmux_spec_socket if external else None)

    @property
    def tmux_window_external(self) -> Any:
        self.ribo_tmux = self.connect_tmux(True)
        from chiasma.io.compute import TmuxIO
        from chiasma.commands.window import windows
        @do(TmuxIO)
        def run() -> Do:
            ws = yield windows()
            yield TmuxIO.from_maybe(ws.head, 'tmux contains no windows')
        return run().unsafe(self.ribo_tmux)

    @property
    def tmux_window_local(self) -> Any:
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
        env_args = self.vim_proc_env.map2(lambda k, v: f'{k}={v}').cons('env')
        cmd = env_args + self.nvim_cmdline
        from chiasma.commands.pane import send_keys
        send_keys(0, List(cmd.join_tokens)).unsafe(self.ribo_tmux)
        wait_for(Path(self.nvim_socket).is_socket)

    def start_neovim_tmux_pane(self) -> None:
        self.ribo_tmux = self.connect_tmux(False)
        env_args = self.vim_proc_env.map2(lambda k, v: f'{k}={v}').cons('env')
        cmd = env_args + self.nvim_cmdline
        pid = os.getpid()
        from chiasma.io.compute import TmuxIO
        from chiasma.command import simple_tmux_cmd_attrs
        from psutil import Process
        @do(TmuxIO)
        def run() -> Do:
            ps = yield simple_tmux_cmd_attrs('list-panes', Nil, List('pane_pid', 'window_id'))
            def match(pane: Map[str, str]) -> bool:
                return Lists.wrap(Process(int(pane['pane_pid'])).children(recursive=True)).map(_.pid).contains(pid)
            current_pane = yield TmuxIO.from_maybe(ps.find(match), 'vim pane not found')
            window_id = current_pane['window_id']
            pane = yield simple_tmux_cmd_attrs('split-window', List('-t', window_id, '-d', '-P') + cmd, List('pane_id'))
            return pane[0]['pane_id'][1:]
        self.tmux_pane_id = run().unsafe(self.ribo_tmux)
        wait_for(Path(self.nvim_socket).is_socket)
        self.neovim = neovim.attach('socket', path=self.nvim_socket)
        self.neovim.command('python3 sys.path.insert(0, \'{}\')'.format(self.python_path))

    def _cleanup_tmux(self) -> None:
        if self.tmux_pane_id is not None and not self.keep_tmux_pane:
            from chiasma.commands.pane import close_pane_id
            close_pane_id(self.tmux_pane_id).unsafe(self.ribo_tmux)

    def create_nvim_api(self, vim: Nvim) -> NvimApi:
        return NativeNvimApi(self.plugin_name(), vim._session)

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
        if self.tmux_nvim_external:
            from chiasma.io.compute import TmuxIO
            TmuxIO.write('kill-server').unsafe(self.ribo_tmux)

    def _pre_start_neovim(self) -> None:
        pass

    def _post_start_neovim(self) -> None:
        rtp = fixture_path('config', 'rtp')
        option_cat('runtimepath', List(rtp)).unsafe(self.vim)
        variable_set_prefixed('debug', True)

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

    def cmd(self, cmd: str, *args: str) -> NvimIO[None]:
        return nvim_command(cmd, *args, verbose=True)

    def json_cmd(self, cmd: str, *args: str, **data: Any) -> NvimIO[None]:
        return json_cmd(cmd, *args, **data)

    @property
    def content(self) -> List[str]:
        return self.vim.buffer.content

    def program_log(self) -> Either[str, List['str']]:
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
        # NvimApi.async = _mock_async
        # NvimApi.main_event_loop = _nop_main_loop
        # NvimApi.proxy = property(_mock_proxy)
        # NvimApi.clean = lambda self: True

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
        define_function(stderr_handler_name, List('id', 'data', 'event'), stderr_handler_body).unsafe(self.vim)
        cmd = f'from ribosome.host import start_module; start_module({self.module()!r})'
        args = ['python3', '-c', cmd]
        opts = dict(rpc=True, on_stderr=stderr_handler_name)
        nvim_call_function('jobstart', args, opts).unsafe(self.vim)

    def send_json(self, data: str) -> None:
        self.vim.call(f'{self.plugin_name()}Send', data)

    def _pre_start(self) -> None:
        if self.autostart_plugin:
            self.pvar_becomes('started', True)


__all__ = ('VimIntegrationSpec', 'ExternalIntegrationSpec', 'AutoPluginIntegrationSpec')
