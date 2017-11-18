from typing import Callable, Any, Optional
from contextlib import contextmanager

from amino import List, Map

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


class MockNvimComponent(object):

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


class MockTab(MockNvimComponent, Tab):
    pass


class MockWindow(MockNvimComponent, Window):
    pass


class MockBuffer(MockNvimComponent, Buffer):
    pass


class MockNvim:

    @property
    def types(self) -> Map[str, type]:
        return Map()

    def command(self, cmdline: str, **kw: Any) -> Any:
        return 0


class MockNvimFacade(MockNvimComponent, NvimFacade):

    def __init__(self, prefix: str='ribosome', vars: dict=dict()) -> None:
        MockNvimComponent.__init__(self, prefix, vars)
        self.vim = MockNvim()
        self.target = self.vim

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

__all__ = ('MockNvimFacade',)
