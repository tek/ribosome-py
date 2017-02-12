from amino import env

from ribosome.test.integration import PluginIntegrationSpec


class IntegrationSpecBase(PluginIntegrationSpec):

    def setup(self):
        self.log_format = '{message}'
        super().setup()

__all__ = ('IntegrationSpecBase',)
