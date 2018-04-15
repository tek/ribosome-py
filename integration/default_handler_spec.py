from kallikrein import Expectation
from kallikrein.matchers import contain

from amino.test import temp_dir

from ribosome.test.integration.klk import AutoPluginIntegrationKlkSpec
from ribosome.config.settings import Settings
from ribosome.config.config import NoData
from ribosome.test.klk import kn
from ribosome.nvim.api.function import nvim_call_tpe
from ribosome.nvim.api.exists import call_once_defined

from integration._support.default_handler import class_name


class DefaultHandlerSpec(AutoPluginIntegrationKlkSpec[Settings, NoData]):
    '''
    append a directory to the plugin's `sys.path` $append_path
    '''

    def plugin_name(self) -> str:
        return 'plug'

    def module(self) -> str:
        return 'integration._support.default_handler'

    def append_path(self) -> Expectation:
        pkg = temp_dir('default_handler', 'pp', 'pkg')
        pp = pkg.parent
        file = pkg / '__init__.py'
        file.write_text(f'class {class_name}: pass')
        call_once_defined('PlugAppendPythonPath', str(pp)).unsafe(self.vim)
        return (
            kn(self.vim, nvim_call_tpe, str, 'TestPath').must(contain(class_name)) &
            kn(self.vim, nvim_call_tpe, str, 'PlugShowPythonPath').must(contain(contain(str(pp))))
        )


__all__ = ('DefaultHandlerSpec',)
