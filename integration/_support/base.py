from ribosome.test.integration.klk import PluginIntegrationKlkSpec


class IntegrationSpecBase(PluginIntegrationKlkSpec):

    def setup(self):
        super().setup()
        self.log_format = '{message}'

__all__ = ('IntegrationSpecBase',)
