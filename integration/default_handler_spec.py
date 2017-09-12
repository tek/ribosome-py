from kallikrein import k, Expectation, kf
from kallikrein.matchers.either import be_right

from amino import Right, Either
from amino.test import temp_dir

from ribosome import NvimPlugin
from ribosome.request import function

from integration._support.base import IntegrationSpecBase

class_name = 'ZeeKlass'


class DefaultHandlerSpecPlugin(NvimPlugin, name='plug'):

    @function()
    def test_path(self) -> str:
        return Either.import_name('pkg', class_name).map(lambda a: a.__name__).value_or('failed')


class DefaultHandlerSpec(IntegrationSpecBase):
    '''
    test $test
    '''

    @property
    def plugin_class(self) -> Either[str, type]:
        return Right(DefaultHandlerSpecPlugin)

    def test(self) -> Expectation:
        pkg = temp_dir('default_handler', 'pp', 'pkg')
        pp = pkg.parent
        file = pkg / '__init__.py'
        file.write_text(f'class {class_name}: pass')
        self.cmd_sync('PlugAppendPythonPath', str(pp))
        return kf(self.vim.call, 'TestPath').must(be_right(class_name))

__all__ = ('DefaultHandlerSpec',)
