from kallikrein import Expectation

from amino.test.path import fixture_path
from amino import Either, Right
from amino.util.mod import class_path

from ribosome.rpc import define_handlers, rpc_handlers
from ribosome.test.integration.klk import PluginIntegrationKlkSpec

from integration._support.plugin import TestPluginUnlooped


class HostSpec(PluginIntegrationKlkSpec):
    '''start a host from its class path $start_host
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
        cls = self.plugin_class.get_or_raise
        plug = self.rplugin_path.get_or_raise
        channel = self.vim.call(
            'jobstart',
            ['python', str(exe), str(plug), class_path(cls)],
            dict(rpc=True)
        ).get_or_raise
        handlers = rpc_handlers(self.plugin_class.get_or_raise)
        define_handlers(channel, handlers, 'host', str(plug)).attempt(self.vim).get_or_raise
        return self.command_exists('Go')

__all__ = ('HostSpec',)
