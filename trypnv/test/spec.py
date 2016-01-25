from typing import Callable, Any
from contextlib import contextmanager

from flexmock import flexmock  # type: ignore

from tryp import may, Maybe, List
from tryp.test import Spec

import trypnv
from trypnv.nvim import Buffer, Tab, Window
from trypnv import NvimFacade


class MockNvim(object):

    @property
    def window(self):
        return MockWindow(self.vim, None, self.prefix)

    @property
    def buffer(self):
        return MockBuffer(self.vim, None, self.prefix)

    @property
    def tab(self):
        return MockTab(self.vim, None, self.prefix)

    def set_option(self, *a, **kw):
        pass

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
        self.vars = {}
        super().__init__(None, prefix)
        self.target = self

    @may
    def var(self, name: str) -> Maybe[str]:  # type: ignore
        v = self.vars.get(name)
        if v is None:
            ignore_names = ['_machine', '_message',
                            '{}__message'.format(self.prefix),
                            '{}__machine'.format(self.prefix),
                            ]
            if name not in ignore_names:
                self.log.error('variable not found: {}'.format(name))
        return v

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
        trypnv.in_vim = False
        self.vim = MockNvimFacade(self.prefix)
        self.vim_mock = flexmock(self.vim)

__all__ = ('MockNvimSpec', 'MockNvimFacade')
