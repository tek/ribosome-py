import time
from datetime import datetime
from typing import Callable, Any

from amino.test.spec import default_timeout
from amino import List

from kallikrein import k, kf
from kallikrein.matcher import Matcher
from kallikrein.matchers.length import have_length
from kallikrein.matchers.comparison import greater
from kallikrein.expectation import Expectation
from kallikrein.matchers import contain

from ribosome.test.integration.spec import VimIntegrationSpecI


def later(exp: Expectation, timeout: float=None, intval: float=0.1) -> None:
    to = default_timeout if timeout is None else timeout
    start = datetime.now()
    while (not exp.unsafe_eval and
           (datetime.now() - start).total_seconds() < to):
        time.sleep(intval)
    return exp


class VimIntegrationKlkHelpers(VimIntegrationSpecI):

    def _log_line(self, index: int, checker: Matcher) -> None:
        def check() -> None:
            minlen = index if index >= 0 else abs(index + 1)
            return (
                k(self._log_out).must(have_length(greater(minlen))) &
                k(self._log_out[index]).must(checker)
            )
        return later(check)

    def _log_contains(self, line: str) -> None:
        return later(lambda: k(self._log_out).must(contain(line)))

    def _buffer_content(self, data: List[str]) -> None:
        return later(lambda: k(self.content) == data)

    def _buffer_length(self, length: int) -> None:
        return later(lambda: k(self.content).must(have_length(length)))

    def _wait_for(self, pred: Callable[..., bool], *a: Any, **kw: Any) -> None:
        return later(kf(pred, *a, **kw).true)

__all__ = ('VimIntegrationKlkHelpers',)
