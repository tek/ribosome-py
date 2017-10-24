from kallikrein import Expectation, kf
from kallikrein.matchers.either import be_right
from kallikrein.matchers import contain

from amino import Right, Either
from amino.test import temp_dir

from ribosome import NvimPlugin, function

from integration._support.base import IntegrationSpecBase

class_name = 'ZeeKlass'


class DefaultHandlerSpecPlugin(NvimPlugin, pname='plug'):

    @function()
    def test_path(self) -> str:
        return Either.import_name('pkg', class_name).map(lambda a: a.__name__).value_or('failed')


class DefaultHandlerSpec(IntegrationSpecBase):
    '''
    append a directory to the plugin's `sys.path` $append_path
    '''

    @property
    def _prefix(self) -> str:
        return 'DH'

    @property
    def plugin_class(self) -> Either[str, type]:
        return Right(DefaultHandlerSpecPlugin)

    def append_path(self) -> Expectation:
        pkg = temp_dir('default_handler', 'pp', 'pkg')
        pp = pkg.parent
        file = pkg / '__init__.py'
        file.write_text(f'class {class_name}: pass')
        self.vim.call('PlugAppendPythonPath', str(pp))
        return (
            kf(self.vim.call, 'TestPath').must(be_right(class_name)) &
            kf(self.vim.call, 'PlugShowPythonPath').must(be_right(contain(str(pp))))
        )

__all__ = ('DefaultHandlerSpec',)
