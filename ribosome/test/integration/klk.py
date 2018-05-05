import time
from datetime import datetime
from typing import Callable, Any, Union, TypeVar, Generic

from amino.test.spec import default_timeout
from amino import List

from kallikrein import Expectation, kf
from kallikrein.matcher import BoundMatcher
from kallikrein.matchers.length import have_length
from kallikrein.matchers.comparison import greater
from kallikrein.matchers import contain, equal
from kallikrein.matchers.lines import have_lines
from kallikrein.matchers.maybe import be_just
from kallikrein.matchers.either import be_right

from ribosome.test.klk.expectable import kn
from ribosome.nvim.api.variable import variable_prefixed_raw, variable_raw
from ribosome.nvim.api.exists import command_exists


def later_f(exp: Callable[[], Expectation], timeout: float=None, intval: float=0.1) -> Expectation:
    to = default_timeout if timeout is None else timeout
    start = datetime.now()
    while (not exp().unsafe_eval and (datetime.now() - start).total_seconds() < to):
        time.sleep(intval)
    exp().fatal_eval()
    return exp()


def later(exp: Expectation, timeout: float=None, intval: float=0.1) -> Expectation:
    return later_f(lambda: exp, timeout, intval)


# class VimIntegrationKlkHelpers(VimIntegrationSpecI):

#     def _wait_for(self, pred: Callable[..., bool], *a: Any, **kw: Any) -> Expectation:
#         return later(kf(pred, *a, **kw).true)

#     def _list_line(self, log: Callable[[], List[str]], index: int, matcher: BoundMatcher) -> Expectation:
#         minlen = index if index >= 0 else abs(index + 1)
#         return later(
#             kf(log).must(have_length(greater(minlen))) &
#             kf(lambda: log().lift(index)).must(matcher)
#         )

#     def _log_line(self, index: int, matcher: BoundMatcher) -> Expectation:
#         return self._list_line(lambda: self._log_out, index, matcher)

#     def _log_contains(self, target: Union[str, BoundMatcher[str]]) -> Expectation:
#         matcher = target if isinstance(target, BoundMatcher) else equal(target)
#         return later(kf(lambda: self._log_out).must(contain(matcher)))

#     def _log_equals(self, lines: Union[str, List[str]]) -> Expectation:
#         return later(kf(lambda: self._log_out).must(have_lines(lines)))

#     def _buffer_content(self, data: Union[str, List[str]]) -> Expectation:
#         return later(self.contentkf.must(have_lines(data)))

#     def _buffer_length(self, length: int) -> Expectation:
#         return later(self.contentkf.must(have_length(length)))

#     def _buffer_line(self, index: int, matcher: BoundMatcher) -> Expectation:
#         return self._list_line(lambda: self._buffer_out, index, be_just(matcher))

#     def _buffer_contains(self, line: str) -> Expectation:
#         return later(kf(lambda: self._buffer_out).must(contain(line)))

#     def _buffer_option(self, name: str, value: Any) -> Expectation:
#         return later(kf(lambda: self.buffer.options(name)).must(be_right(value)))

#     def _buffer_name(self, name: str) -> Expectation:
#         return later(kf(lambda: self.buffer.name) == name)

#     def _buffer_count(self, count: int) -> Expectation:
#         return later(kf(lambda: self.vim.buffers).must(have_length(count)))

#     def _window_height(self, height: int) -> Expectation:
#         return later(kf(lambda: self.vim.window.height).must(contain(height)))

#     def _window_count(self, count: int) -> Expectation:
#         return later(kf(lambda: self.vim.windows).must(have_length(count)))

#     def _cursor_line(self, lnum: int) -> Expectation:
#         return later(kf(lambda: self.vim.window.line).must(contain(lnum)))

#     def _messages_contain(self, line: str) -> Expectation:
#         return later(kf(lambda: self.vim.messages).must(contain(line)))

#     def seen_program(self, name: str, **kw) -> Expectation:
#         return later(kf(self.program_log).must(contain(name)), **kw)

#     def var_is(self, name: str, value: Any) -> Expectation:
#         return kn(self.vim, variable_raw, name).must(contain(be_right(value)))

#     def var_becomes(self, name: str, value: Any) -> Expectation:
#         return later(self.var_is(name, value))

#     def pvar_is(self, name: str, value: Any) -> Expectation:
#         return kn(self.vim, variable_prefixed_raw, name).must(contain(be_right(value)))

#     def pvar_becomes(self, name: str, value: Any) -> Expectation:
#         return later(self.pvar_is(name, value))

#     def pvar_becomes_map(self, name: str, value: Any, f: Callable[[Any], Any]) -> Expectation:
#         return later(kf(lambda: self.vim.vars.p(name).map(f)).must(be_right(value)))
#         return self._wait_for(lambda: self.vim.vars.p(name).map(f).contains(value))

#     def command_exists(self, name: str, **kw) -> Expectation:
#         return later(kn(self.vim, command_exists, name).must(contain(True)), **kw)

#     def command_exists_not(self, name: str, **kw: Any) -> Expectation:
#         return later(kn(self.vim, command_exists, name).must(contain(False)), **kw)
