import os
from pathlib import Path
from threading import Thread
import asyncio
from functools import wraps

import neovim  # type: ignore

from tek.test import fixture_path, temp_dir, later  # type: ignore

from tryp import List
from tryp.test import IntegrationSpec as TrypIntegrationSpec

from trypnv.logging import Logging
from trypnv import NvimFacade
from trypnv.nvim import AsyncVimProxy

from proteome.test import Spec


class IntegrationSpec(TrypIntegrationSpec, Spec):

    def setup(self):
        super().setup()
        AsyncVimProxy.allow_async_relay = False


class VimIntegrationSpec(TrypIntegrationSpec, Logging):

    def setup(self):
        self.cwd = Path.cwd()
        super().setup()
        self._debug = False
        self._rplugin_path = None
        self._handlers = []
        self.logfile = temp_dir('log') / self.__class__.__name__
        os.environ['TRYPNV_LOG_FILE'] = str(self.logfile)
        self.vimlog = temp_dir('log') / 'vim'
        self._pre_start_neovim()
        self._start_neovim()
        self._post_start_neovim()
        rtp = fixture_path('config', 'rtp')
        self.vim.amend_optionl('runtimepath', rtp)
        self._setup_handlers()
        self._pre_start()

    def _start_neovim(self):
        ''' start an embedded vim session that loads no init.vim.
        **self.vimlog** is set as log file. aside from being convenient,
        this is crucially necessary, as the first use of the session
        will block if stdout is used for output.
        '''
        argv = ['nvim', '--embed', '-V{}'.format(self.vimlog), '-u', 'NONE']
        self.neovim = neovim.attach('child', argv=argv)
        self.vim = NvimFacade(self.neovim)

    def _setup_handlers(self):
        self.vim.call(
            'remote#host#RegisterPlugin',
            'python3',
            str(self._rplugin_path),
            self._handlers,
        )

    # FIXME quitting neovim blocks sometimes
    # without quitting, specs with subprocesses block in the end
    def teardown(self):
        # self.neovim.quit()
        os.chdir(str(self.cwd))
        if self._debug:
            self._log_out.foreach(self.log.info)

    def _pre_start_neovim(self):
        pass

    def _post_start_neovim(self):
        pass

    def _pre_start(self):
        pass

    def _pvar_becomes(self, name, value):
        return self._wait_for(lambda: self.vim.pvar(name).contains(value))

    @property
    def _log_out(self):
        return List.wrap(self.logfile.read_text().splitlines())

    def _log_line(self, index, checker):
        def check():
            len(self._log_out).should.be.greater_than(abs(index))
            return checker(self._log_out[index]).should.be.ok
        later(check)


def main_looped(fun):
    @wraps(fun)
    def wrapper(self):
        loop = asyncio.get_event_loop()
        done = asyncio.Future(loop=loop)

        def runner():
            fun(self)
            loop.call_soon_threadsafe(lambda: done.set_result(True))
        Thread(target=runner).start()
        loop.run_until_complete(done)
    return wrapper

__all__ = ('IntegrationSpec')
