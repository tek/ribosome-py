import time
from datetime import datetime
from typing import Callable, Any, Union, Type, TypeVar, Generic

from amino.test.spec import default_timeout
from amino import List, __

from kallikrein import Expectation, kf
from kallikrein.expectable import Expectable
from kallikrein.matcher import BoundMatcher
from kallikrein.matchers.length import have_length
from kallikrein.matchers.comparison import greater
from kallikrein.matchers import contain, equal
from kallikrein.matchers.lines import have_lines
from kallikrein.matchers.maybe import be_just
from kallikrein.matchers.either import be_right

from ribosome.test.integration.spec import (VimIntegrationSpecI, VimIntegrationSpec, ExternalIntegrationSpec,
                                            AutoPluginIntegrationSpec)
from ribosome.nvim.components import Buffer
from ribosome.config.settings import Settings


def later_f(exp: Callable[[], Expectation], timeout: float=None, intval: float=0.1) -> Expectation:
    to = default_timeout if timeout is None else timeout
    start = datetime.now()
    while (not exp().unsafe_eval and (datetime.now() - start).total_seconds() < to):
        time.sleep(intval)
    exp().fatal_eval()
    return exp()


def later(exp: Expectation, timeout: float=None, intval: float=0.1) -> None:
    return later_f(lambda: exp, timeout, intval)


class VimIntegrationKlkHelpers(VimIntegrationSpecI):

    def _wait_for(self, pred: Callable[..., bool], *a: Any, **kw: Any) -> Expectation:
        return later(kf(pred, *a, **kw).true)

    @property
    def buffer(self) -> Buffer:
        return self.vim.buffer

    @property
    def _buffer_out(self) -> List[str]:
        return self.buffer.content

    @property
    def contentkf(self) -> Expectable:
        return kf(lambda: self._buffer_out)

    def _list_line(self, log: Callable[[], List[str]], index: int, matcher: BoundMatcher) -> Expectation:
        minlen = index if index >= 0 else abs(index + 1)
        return later(
            kf(log).must(have_length(greater(minlen))) &
            kf(lambda: log().lift(index)).must(matcher)
        )

    def _log_line(self, index: int, matcher: BoundMatcher) -> Expectation:
        return self._list_line(lambda: self._log_out, index, matcher)

    def _log_contains(self, target: Union[str, BoundMatcher[str]]) -> Expectation:
        matcher = target if isinstance(target, BoundMatcher) else equal(target)
        return later(kf(lambda: self._log_out).must(contain(matcher)))

    def _log_equals(self, lines: Union[str, List[str]]) -> Expectation:
        return later(kf(lambda: self._log_out).must(have_lines(lines)))

    def _buffer_content(self, data: Union[str, List[str]]) -> Expectation:
        return later(self.contentkf.must(have_lines(data)))

    def _buffer_length(self, length: int) -> Expectation:
        return later(self.contentkf.must(have_length(length)))

    def _buffer_line(self, index: int, matcher: BoundMatcher) -> Expectation:
        return self._list_line(lambda: self._buffer_out, index, be_just(matcher))

    def _buffer_contains(self, line: str) -> Expectation:
        return later(kf(lambda: self._buffer_out).must(contain(line)))

    def _buffer_option(self, name: str, value: Any) -> Expectation:
        return later(kf(lambda: self.buffer.options(name)).must(be_right(value)))

    def _buffer_name(self, name: str) -> Expectation:
        return later(kf(lambda: self.buffer.name) == name)

    def _buffer_count(self, count: int) -> Expectation:
        return later(kf(lambda: self.vim.buffers).must(have_length(count)))

    def _window_height(self, height: int) -> Expectation:
        return later(kf(lambda: self.vim.window.height).must(contain(height)))

    def _window_count(self, count: int) -> Expectation:
        return later(kf(lambda: self.vim.windows).must(have_length(count)))

    def _cursor_line(self, lnum: int) -> Expectation:
        return later(kf(lambda: self.vim.window.line).must(contain(lnum)))

    def _messages_contain(self, line: str) -> Expectation:
        return later(kf(lambda: self.vim.messages).must(contain(line)))

    def seen_trans(self, name: str, **kw) -> Expectation:
        return later(kf(self.trans_log).must(be_right(contain(name))), **kw)

    def var_is(self, name: str, value: Any) -> Expectation:
        return kf(self.vim.vars, name).must(be_right(value))

    def var_becomes(self, name: str, value: Any) -> Expectation:
        return later(self.var_is(name, value))

    def pvar_is(self, name: str, value: Any) -> Expectation:
        return kf(self.vim.vars.p, name).must(be_right(value))

    def pvar_becomes(self, name: str, value: Any) -> Expectation:
        return later(self.pvar_is(name, value))

    def pvar_becomes_map(self, name: str, value: Any, f: Callable[[Any], Any]) -> Expectation:
        return later(kf(lambda: self.vim.vars.p(name).map(f)).must(be_right(value)))
        return self._wait_for(lambda: self.vim.vars.p(name).map(f).contains(value))

    def command_exists(self, name: str, **kw) -> Expectation:
        return later(kf(self.vim.command_exists, name).true, **kw)

    def command_exists_not(self, name: str, **kw: Any) -> Expectation:
        return later(kf(self.vim.command_exists, name).false, **kw)


class VimIntegrationKlkSpec(VimIntegrationSpec, VimIntegrationKlkHelpers):
    pass


class ExternalIntegrationKlkSpec(ExternalIntegrationSpec, VimIntegrationKlkHelpers):
    pass


D = TypeVar('D')
S = TypeVar('S', bound=Settings)


class AutoPluginIntegrationKlkSpec(Generic[S, D], AutoPluginIntegrationSpec[S, D], VimIntegrationKlkHelpers):
    pass

__all__ = ('VimIntegrationKlkHelpers', 'VimIntegrationKlkSpec', 'ExternalIntegrationKlkSpec',
           'AutoPluginIntegrationKlkSpec')
