from typing import Callable, Any, Optional
from contextlib import contextmanager

from flexmock import flexmock

from amino import List
from amino.test.spec_spec import Spec

import ribosome
from ribosome.nvim import Buffer, Tab, Window
from ribosome import NvimFacade
from ribosome.nvim.components import Options, Vars


class MockOptions(Options):

    def set(self, *a, **kw):
        pass


class MockVars(Vars):

    def __init__(self, vim, vars: dict) -> None:
        super().__init__(vim)
        self.vars = vars
        self.prefix = vim.prefix

    def _get(self, name: str) -> Optional[Any]:
        return self.vars.get(name)

    def set(self, name, value):
        self.vars[name] = value


class MockNvim(object):

    def __init__(self, prefix, vars: dict) -> None:
        self.prefix = prefix
        self._vars = MockVars(self, vars)
        self._options = MockOptions(self)

    @property
    def window(self):
        return MockWindow(self.vim, None, self.prefix)

    @property
    def buffer(self):
        return MockBuffer(self.vim, None, self.prefix)

    @property
    def tab(self):
        return MockTab(self.vim, None, self.prefix)

    def cmd(self, *a, **kw):
        pass


class MockTab(MockNvim, Tab):
    pass


class MockWindow(MockNvim, Window):
    pass


class MockBuffer(MockNvim, Buffer):
    pass


class MockNvimFacade(MockNvim, NvimFacade):

    def __init__(self, prefix: str, vars: dict=dict()) -> None:
        MockNvim.__init__(self, prefix, vars)
        self.target = self

    @property
    def windows(self):
        return List()

    def switch_root(self, root):
        pass

    def async(self, f: Callable[['NvimFacade'], Any], *a, **kw):
        return f(self, *a, **kw)

    @contextmanager
    def main_event_loop(self):
        yield None

    def reload_windows(self):
        pass


class MockNvimSpec(Spec):

    def __init__(self, prefix):
        Spec.__init__(self)
        self.prefix = prefix

    def setup(self):
        Spec.setup(self)
        ribosome.in_vim = False
        self.vim = MockNvimFacade(self.prefix)
        self.vim_mock = flexmock(self.vim)

__all__ = ('MockNvimSpec', 'MockNvimFacade')
