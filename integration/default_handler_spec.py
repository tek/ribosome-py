from kallikrein import Expectation, kf
from kallikrein.matchers.either import be_right
from kallikrein.matchers import contain

from amino.test import temp_dir

from ribosome.test.integration.klk import AutoPluginIntegrationKlkSpec
from ribosome.config.settings import Settings
from ribosome.config.config import NoData

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
        self.vim.call_once_defined('PlugAppendPythonPath', str(pp))
        return (
            kf(self.vim.call, 'TestPath').must(be_right(class_name)) &
            kf(self.vim.call, 'PlugShowPythonPath').must(be_right(contain(str(pp))))
        )


__all__ = ('DefaultHandlerSpec',)
