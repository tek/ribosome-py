from typing import Callable, Any
from contextlib import contextmanager

from flexmock import flexmock  # type: ignore

from tryp import may, Maybe, List
from tryp.test import Spec

from trypnv.nvim import Buffer
from trypnv import NvimFacade


class MockNvimFacade(NvimFacade):

    def __init__(self):
        self.vars = {}
        super(MockNvimFacade, self).__init__(None)
        self.target = self

    @may
    def var(self, name: str) -> Maybe[str]:  # type: ignore
        v = self.vars.get(name)
        if v is None:
            self.log.error('variable not found: {}'.format(name))
        return v

    @property
    def buffer(self):
        return Buffer(self, self, self.prefix)

    @property
    def windows(self):
        return List()

    def switch_root(self, root):
        pass

    def async(self, f: Callable[['NvimFacade'], Any]):
        return f(self)

    @contextmanager
    def main_event_loop(self):
        yield

    def cmd(self, *a, **kw):
        pass


class MockNvimSpec(Spec):

    def setup(self, *a, **kw):
        super(MockNvimSpec, self).setup(*a, **kw)
        self.vim = MockNvimFacade()
        self.vim_mock = flexmock(self.vim)

__all__ = ('MockNvimSpec', 'MockNvimFacade')
