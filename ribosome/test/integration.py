import os
import json
import asyncio
from pathlib import Path
from functools import wraps
from threading import Thread
from contextlib import contextmanager

import neovim

from amino.test import fixture_path, temp_dir, later, temp_file

from amino import List, Maybe, Either, Left, __, Map, Try, L, _
from amino.test import IntegrationSpec as IntegrationSpecBase

import ribosome
from ribosome.logging import Logging, log
from ribosome import NvimFacade
from ribosome.nvim import AsyncVimProxy
from ribosome.test.fixtures import rplugin_template

from libtmux import Pane

from amino import env
from amino.lazy import lazy
from amino.test.path import base_dir


class IntegrationSpec(IntegrationSpecBase):

    def setup(self):
        super().setup()
        AsyncVimProxy.allow_async_relay = False


class VimIntegrationSpec(IntegrationSpecBase, Logging):

    def __init__(self) -> None:
        super().__init__()
        self.tmux_nvim = 'RIBOSOME_TMUX_SPEC' in env
        self._tmux_pane = None
        self.keep_tmux_pane = False
        self.vimlog = temp_dir('log') / 'vim'
        self._cmdline = ('nvim', '-V{}'.format(self.vimlog), '-n', '-u',
                         'NONE')

    def setup(self):
        super().setup()
        self._debug = 'RIBOSOME_DEVELOPMENT' in env
        self.logfile = temp_dir('log') / self.__class__.__name__
        self.logfile.touch()
        os.environ['RIBOSOME_LOG_FILE'] = str(self.logfile)
        self._pre_start_neovim()
        self._start_neovim()
        self._post_start_neovim()
        self._pre_start()

    def _start_neovim(self):
        if self.tmux_nvim:
            self._start_neovim_tmux()
        else:
            self._start_neovim_embedded()
        self.vim = self._nvim_facade(self.neovim)

    def _start_neovim_embedded(self):
        ''' start an embedded vim session that loads no init.vim.
        **self.vimlog** is set as log file. aside from being convenient,
        this is crucially necessary, as the first use of the session
        will block if stdout is used for output.
        '''
        argv = self._cmdline + ('--embed',)
        self.neovim = neovim.attach('child', argv=argv)

    @lazy
    def nvim_socket(self):
        return str(temp_dir('nvim_sockets') / List.random_string())

    @property
    def project_path(self):
        return str(base_dir().parent)

    @lazy
    def _tmux_window(self):
        try:
            import libtmux
        except ImportError:
            raise Exception('install libtmux to run nvim in a tmux pane')
        else:
            server = libtmux.Server()
            session = next(s for s in server.sessions
                           if int(s['session_attached']) >= 1)
            return session.attached_window

    def _start_neovim_tmux(self):
        path = self.project_path
        env = (
            'env',
            'NVIM_LISTEN_ADDRESS={}'.format(self.nvim_socket),
            'PYTHONPATH={}'.format(path),
            'RIBOSOME_LOG_FILE={}'.format(self.logfile),
        )
        cmd = tuple(env + self._cmdline)
        out = self._tmux_window.cmd(
            'split-window', '-d', '-P', '-F#{pane_id}', *cmd).stdout
        self._tmux_pane = Pane(self._tmux_window, pane_id=out[0])
        self.neovim = neovim.attach('socket', path=self.nvim_socket)
        self.neovim.command('python3 sys.path.insert(0, \'{}\')'.format(path))

    def _cleanup_tmux(self):
        if self._tmux_pane is not None and not self.keep_tmux_pane:
            self._tmux_pane.cmd('kill-pane')

    def _nvim_facade(self, vim):
        return NvimFacade(vim, self._prefix)

    @property
    def _prefix(self):
        return ''

    # FIXME quitting neovim blocks sometimes
    # without quitting, specs with subprocesses block in the end
    def teardown(self):
        # self.neovim.quit()
        if self._debug:
            self._log_out.foreach(self.log.info)
        if self.tmux_nvim:
            self._cleanup_tmux()

    def _pre_start_neovim(self):
        pass

    def _post_start_neovim(self):
        rtp = fixture_path('config', 'rtp')
        self.vim.options.amend_l('runtimepath', rtp)

    def _pre_start(self):
        pass

    def _pvar_becomes(self, name, value):
        return self._wait_for(lambda: self.vim.vars.p(name).contains(value))

    def _pvar_becomes_map(self, name, value, f):
        return self._wait_for(
            lambda: self.vim.vars.p(name).map(f).contains(value))

    @property
    def _log_out(self):
        return List.wrap(self.logfile.read_text().splitlines())

    def _log_line(self, index, checker):
        def check():
            minlen = index if index >= 0 else abs(index + 1)
            len(self._log_out).should.be.greater_than(minlen)
            return checker(self._log_out[index]).should.be.ok
        later(check)

    def _log_contains(self, line):
        later(lambda: self._log_out.should.contain(line))

    def _json_cmd(self, cmd, data):
        j = json.dumps(data).replace('"', '\\"')
        return '{} {}'.format(cmd, j)

    def json_cmd(self, cmd, **data):
        self.vim.cmd(self._json_cmd(cmd, data))

    def json_cmd_sync(self, cmd, **data):
        return self.vim.cmd_sync(self._json_cmd(cmd, data))


def main_looped(fun):
    @wraps(fun)
    def wrapper(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        done = asyncio.Future(loop=loop)
        def runner():
            local_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(local_loop)
            Try(fun, self).leffect(L(log.caught_exception)('spec', _))
            loop.call_soon_threadsafe(lambda: done.set_result(True))
            local_loop.close()
        Thread(target=runner).start()
        loop.run_until_complete(done)
        loop.close()
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
        super().teardown()
        if self.root is not None:
            self.root.stop(shutdown=False)
            if self._debug:
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

__all__ = ('IntegrationSpec', 'VimIntegrationSpec', 'PluginIntegrationSpec')
