import sure  # NOQA
from flexmock import flexmock  # NOQA

from tryp.test.path import fixture_path

from trypnv.test import VimIntegrationSpec


class PluginSpec(VimIntegrationSpec):

    def _pre_start_neovim(self):
        self.rtp = fixture_path('nvim_plugin')
        self._rplugin_path = (self.rtp / 'rplugin' / 'python3' /
                              'test_plug.py')
        self._handlers = [
            {
                'sync': 1,
                'name': 'Go',
                'type': 'command',
                'opts': {'nargs': 0},
            },
        ]

    def startup(self):
        self._debug = True
        self.vim.cmd_sync('Go')

__all__ = ('PluginSpec',)
