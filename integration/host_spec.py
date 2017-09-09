from kallikrein import Expectation, kf, k
from kallikrein.matchers.either import be_right

from amino.test.path import fixture_path
from amino import Either, Right

from ribosome.rpc import define_handlers, rpc_handlers
from ribosome.test.integration.klk import PluginIntegrationKlkSpec, later

from integration._support.plugin import TestPluginUnlooped


class HostSpec(PluginIntegrationKlkSpec):
    '''start a host from its class file $start_host
    '''

    @property
    def _prefix(self) -> str:
        return 'host'

    @property
    def autostart_plugin(self) -> bool:
        return False

    @property
    def plugin_class(self) -> Either[str, type]:
        return Right(TestPluginUnlooped)

    def start_host(self) -> Expectation:
        exe = fixture_path('host', 'run')
        plug = self.rplugin_path.get_or_raise
        channel = self.vim.call(
            'jobstart',
            ['python3', str(exe), str(plug)],
            dict(rpc=True)
        ).get_or_raise
        handlers = rpc_handlers(self.plugin_class.get_or_raise)
        define_handlers(channel, handlers, 'host', str(plug)).attempt(self.vim).get_or_raise
        self._wait(.2)
        self.command_exists('Go')
        return later(kf(self.cmd_sync, 'Go').must(be_right))

__all__ = ('HostSpec',)
