from ribosome.test.integration.klk import PluginIntegrationKlkSpec


class IntegrationSpecBase(PluginIntegrationKlkSpec):

    def setup(self):
        self.log_format = '{message}'
        super().setup()

__all__ = ('IntegrationSpecBase',)
