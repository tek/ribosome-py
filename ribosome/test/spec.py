from typing import Callable, Any
from contextlib import contextmanager

from flexmock import flexmock

from amino import may, Maybe, List
from amino.test import Spec

import ribosome
from ribosome.nvim import Buffer, Tab, Window
from ribosome import NvimFacade
from ribosome.nvim.components import Options, Vars


class MockOptions(Options):

    def set(self, *a, **kw):
        pass


class MockVars(Vars):

    def __init__(self, vim) -> None:
        super().__init__(vim)
        self.vars = dict()
        self.prefix = vim.prefix

    @may
    def __call__(self, name: str) -> Maybe[str]:  # type: ignore
        v = self.vars.get(name)
        if v is None:
            ignore_names = ['_machine', '_message',
                            '{}__message'.format(self.prefix),
                            '{}__machine'.format(self.prefix),
                            ]
            if name not in ignore_names:
                self.log.error('variable not found: {}'.format(name))
        return v

    def set(self, name, value):
        self.vars[name] = value


class MockNvim(object):

    def __init__(self, prefix) -> None:
        self.prefix = prefix
        self._vars = MockVars(self)
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

    def __init__(self, prefix):
        MockNvim.__init__(self, prefix)
        self.target = self

    @property
    def windows(self):
        return List()

    def switch_root(self, root):
        pass

    def async(self, f: Callable[['NvimFacade'], Any]):
        return f(self)

    @contextmanager
    def main_event_loop(self):
        yield None

    def reload_windows(self):
        pass


class MockNvimSpec(Spec):

    def __init__(self, prefix):
        super().__init__()
        self.prefix = prefix

    def setup(self):
        super().setup()
        ribosome.in_vim = False
        self.vim = MockNvimFacade(self.prefix)
        self.vim_mock = flexmock(self.vim)

__all__ = ('MockNvimSpec', 'MockNvimFacade')
