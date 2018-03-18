from ribosome.test.integration.klk import VimIntegrationKlkSpec
from ribosome.test.config import default_config_name


class ExternalSpec(VimIntegrationKlkSpec):

    def plugin_name(self) -> str:
        return default_config_name


__all__ = ('ExternalSpec',)
