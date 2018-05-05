from kallikrein import Expectation, k
from kallikrein.matchers import contain
from kallikrein.matchers.tuple import tupled

from amino.test import temp_dir
from amino.test.spec import SpecBase
from amino import do, Do

from ribosome.nvim.api.function import nvim_call_tpe, nvim_call_function, nvim_call_cons
from ribosome.test.integration.embed import TestConfig, plugin_test
from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.util import cons_checked_list

from integration._support.default_handler import class_name, default_handler_spec_config


test_config = TestConfig.cons(default_handler_spec_config)


@do(NvimIO[Expectation])
def append_path_spec() -> Do:
    pkg = temp_dir('default_handler', 'pp', 'pkg')
    pp = pkg.parent
    file = pkg / '__init__.py'
    file.write_text(f'class {class_name}: pass')
    yield nvim_call_function('PlugAppendPythonPath', str(pp))
    name = yield nvim_call_tpe(str, 'TestPath')
    path = yield nvim_call_cons(cons_checked_list(str, lambda a: a), 'PlugShowPythonPath')
    return k((name, path)).must(tupled(2)((contain(class_name), contain(str(pp)))))


class DefaultHandlerSpec(SpecBase):
    '''
    append a directory to the plugin's `sys.path` $append_path
    '''

    def append_path(self) -> Expectation:
        return plugin_test(test_config, append_path_spec)


__all__ = ('DefaultHandlerSpec',)
