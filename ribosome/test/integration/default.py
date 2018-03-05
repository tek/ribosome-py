from ribosome.test.integration.klk import VimIntegrationKlkSpec
from ribosome.test.config import default_config_name


class ExternalSpec(VimIntegrationKlkSpec):

    @property
    def plugin_name(self) -> str:
        return default_config_name

    def plugin_prefix(self) -> str:
        return default_config_name


__all__ = ('ExternalSpec',)
