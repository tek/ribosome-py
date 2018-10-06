from kallikrein import Expectation
from kallikrein.matchers.comparison import eq

from ribosome.test.klk.expectation import await_k_with
from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.ui import current_cursor


def current_cursor_is(line: int, col: int) -> NvimIO[Expectation]:
    return await_k_with(eq((line, col)), current_cursor)


__all__ = ('current_cursor_is',)
