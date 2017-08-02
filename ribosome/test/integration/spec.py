import os
import abc
import json
import asyncio
from functools import wraps
from threading import Thread
from contextlib import contextmanager
from typing import Any

import neovim
from neovim.api import Nvim

from amino.test import fixture_path, temp_dir, temp_file

from amino import List, Maybe, Either, Left, __, Map, env, Path
from amino.lazy import lazy
from amino.test.path import base_dir, pkg_dir
from amino.test.spec import IntegrationSpecBase as AminoIntegrationSpecBase

import ribosome
from ribosome.logging import Logging
from ribosome import NvimFacade
from ribosome.nvim import AsyncVimProxy
from ribosome.test.fixtures import rplugin_template


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
        self._tmux_pane = None
        self.keep_tmux_pane = False
        self.vimlog = temp_dir('log') / 'vim'
        self._cmdline = ('nvim', '-V{}'.format(self.vimlog), '-n', '-u', 'NONE')
        self.log_format = '{levelname} {name}:{message}'

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
        self._start_neovim()
        self._post_start_neovim()
        self._pre_start()
        self._start_plugin()
        self._post_start()

    def _start_neovim(self) -> None:
        asyncio.get_child_watcher().attach_loop(asyncio.get_event_loop())
        if self.tmux_nvim:
            self._start_neovim_tmux()
        else:
            self._start_neovim_embedded()
        self.vim = self._nvim_facade(self.neovim)

    def _start_neovim_embedded(self) -> None:
        ''' start an embedded vim session that loads no init.vim.
        **self.vimlog** is set as log file. aside from being convenient,
        this is crucially necessary, as the first use of the session
        will block if stdout is used for output.
        '''
        argv = self._cmdline + ('--embed',)
        self.neovim = neovim.attach('child', argv=argv)

    @lazy
    def nvim_socket(self) -> str:
        return str(temp_dir('nvim_sockets') / List.random_string())

    @property
    def project_path(self) -> str:
        return str(base_dir().parent)

    @lazy
    def _tmux_window(self) -> Any:
        try:
            import libtmux
        except ImportError:
            raise Exception('install libtmux to run nvim in a tmux pane')
        else:
            server = libtmux.Server()
            session = next(s for s in server.sessions
                           if int(s['session_attached']) >= 1)
            return session.attached_window

    def _start_neovim_tmux(self) -> None:
        from libtmux import Pane
        global_path = env['PYTHONPATH'] | ''
        path = '{}:{}'.format(self.project_path, global_path)
        tmux_env = (
            'env',
            'NVIM_LISTEN_ADDRESS={}'.format(self.nvim_socket),
            'PYTHONPATH={}'.format(path),
            'RIBOSOME_LOG_FILE={}'.format(self.logfile),
            'RIBOSOME_FILE_LOG_FMT=\'{}\''.format(self.log_format),
        )
        cmd = tuple(tmux_env + self._cmdline)
        out = self._tmux_window.cmd(
            'split-window', '-d', '-P', '-F#{pane_id}', *cmd).stdout
        self._tmux_pane = Pane(self._tmux_window, pane_id=out[0])
        self.neovim = neovim.attach('socket', path=self.nvim_socket)
        self.neovim.command('python3 sys.path.insert(0, \'{}\')'.format(path))

    def _cleanup_tmux(self) -> None:
        if self._tmux_pane is not None and not self.keep_tmux_pane:
            self._tmux_pane.cmd('kill-pane')

    def _nvim_facade(self, vim: Nvim) -> NvimFacade:
        return NvimFacade(vim, self._prefix)

    @property
    def _prefix(self) -> str:
        return ''

    def teardown(self) -> None:
        IntegrationSpecBase.teardown(self)
        if self._debug:
            self._log_out.foreach(self.log.info)
        if self.tmux_nvim:
            self._cleanup_tmux()

    def _pre_start_neovim(self) -> None:
        pass

    def _post_start_neovim(self) -> None:
        rtp = fixture_path('config', 'rtp')
        self.vim.options.amend_l('runtimepath', rtp)

    def _pre_start(self) -> None:
        pass

    def _start_plugin(self) -> None:
        pass

    def _post_start(self) -> None:
        pass

    def _pvar_becomes(self, name, value) -> None:
        return self._wait_for(lambda: self.vim.vars.p(name).contains(value))

    def _pvar_becomes_map(self, name, value, f) -> None:
        return self._wait_for(
            lambda: self.vim.vars.p(name).map(f).contains(value))

    @property
    def _log_out(self) -> List[str]:
        return List.wrap(self.logfile.read_text().splitlines())

    def _json_cmd(self, cmd: str, data: dict) -> str:
        j = json.dumps(data).replace('"', '\\"')
        return '{} {}'.format(cmd, j)

    def json_cmd(self, cmd: str, **data: str) -> Either[Exception, str]:
        return self.vim.cmd(self._json_cmd(cmd, data))

    def json_cmd_sync(self, cmd: str, **data: str) -> Either[Exception, str]:
        return self.vim.cmd_sync(self._json_cmd(cmd, data))

    @property
    def content(self) -> List[str]:
        return self.vim.buffer.content


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
        cls = self.plugin_class.get_or_raise
        self.plugin = cls(self.neovim)

    def _await(self):
        if self.root is not None:
            self.root.await_state()

    @property
    def root(self):
        return self.plugin.state

    def teardown(self):
        VimIntegrationSpec.teardown(self)
        if self.root is not None:
            self.root.stop(shutdown=False)
            if self._debug and self._report_expensive:
                self._report()

    def _report(self):
        self.root.sub.cat(self.root) % __.report()


class PluginIntegrationSpec(VimIntegrationSpec):

    def _post_start_neovim(self):
        super()._post_start_neovim()
        self._setup_handlers()

    def _setup_handlers(self):
        rp_path = self.rplugin_path.get_or_raise
        rp_handlers = self.handlers.get_or_raise
        self.vim.call(
            'remote#host#RegisterPlugin',
            'python3',
            str(rp_path),
            rp_handlers,
        )

    @property
    def plugin_class(self) -> Either[str, type]:
        name = self.__class__.__name__
        e = 'property {}.plugin_class must return amino.Right(YourPluginClass)'
        return Left(e.format(name))

    @property
    def rplugin_path(self) -> Either[str, Path]:
        return self.plugin_class / self._auto_rplugin

    @property
    def handlers(self):
        return self.plugin_class / self._auto_handlers

    def _auto_handlers(self, cls):
        import inspect
        return List.wrap(inspect.getmembers(cls)).flat_map2(self._auto_handler)

    def _auto_handler(self, method_name, fun):
        fix = lambda v: int(v) if isinstance(v, bool) else v
        m = Maybe(getattr(fun, '_nvim_rpc_spec', None))
        return m / Map / __.valmap(fix)

    def _auto_rplugin(self, cls):
        mod = cls.__module__
        name = cls.__name__
        rp_path = temp_file('ribosome', 'spec', 'plugin.py')
        rp_path.write_text(rplugin_template.format(plugin_module=mod,
                                                   plugin_class=name))
        return rp_path

__all__ = ('VimIntegrationSpec', 'PluginIntegrationSpec')
