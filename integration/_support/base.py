from amino import env

from ribosome.test.integration import PluginIntegrationSpec


class IntegrationSpecBase(PluginIntegrationSpec):

    def setup(self):
        env['RIBOSOME_FILE_LOG_FMT'] = '{message}'
        super().setup()

__all__ = ('IntegrationSpecBase',)
