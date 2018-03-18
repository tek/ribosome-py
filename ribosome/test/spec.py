from typing import Callable, Any, Optional
from contextlib import contextmanager

from amino import List, Map, Boolean, Maybe, Just, Nil
from amino.util.fun import format_funcall

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


class MockTab(MockNvimComponent, Tab):
    pass


class MockWindow(MockNvimComponent, Window):
    pass


class MockBuffer(MockNvimComponent, Buffer):
    pass


class MockSession:

    def request(self, *a, **kw) -> None:
        pass


class MockNvim:

    def __init__(self, responses: Callable[[str], Any]) -> None:
        self.responses = responses
        self.channel_id = 1
        self.request_log = Nil

    @property
    def types(self) -> Map[str, type]:
        return Map()

    def command(self, cmdline: str, **kw: Any) -> Any:
        self.log_request(cmdline)
        return self.responses(cmdline).get_or_fail(f'no response recorded for command {cmdline}')

    def call(self, name: str, *a: Any, **kw: Any) -> Any:
        rep = format_funcall(name, a, kw)
        self.log_request(rep)
        return self.responses(name).get_or_fail(f'no response recorded for call {rep}')

    def async_call(self, f: Callable[['MockNvim'], None]) -> None:
        pass

    def log_request(self, line: str) -> None:
        self.request_log = self.request_log.cat(line)

    @property
    def _session(self) -> MockSession:
        return MockSession()


class MockNvimFacade(MockNvimComponent, NvimFacade):

    def __init__(self, prefix: str='ribosome', vars: dict=dict(),
                 responses: Callable[[str], Maybe[Any]]=lambda a: Just(0)) -> None:
        MockNvimComponent.__init__(self, prefix, vars)
        self.vim = MockNvim(responses)
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

    def function_exists(self, name: str) -> Boolean:
        return self.vim.responses(name).present

__all__ = ('MockNvimFacade',)
