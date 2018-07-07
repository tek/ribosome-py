from typing import Union

from amino import List

from ribosome.nvim.io.compute import NvimIO
from ribosome.test.klk.expectation import await_k_with
from ribosome.nvim.api.ui import current_buffer_content, buffers

from kallikrein import Expectation
from kallikrein.matchers.lines import have_lines
from kallikrein.matchers.length import have_length
from kallikrein.matcher import Matcher


def current_buffer_matches(matcher: Matcher[List[str]]) -> NvimIO[Expectation]:
    return await_k_with(matcher, current_buffer_content)


def current_buffer_contains(lines: Union[str, List[str]]) -> NvimIO[Expectation]:
    return current_buffer_matches(have_lines(lines))


def buffer_count_is(count: int) -> NvimIO[Expectation]:
    return await_k_with(have_length(count), buffers)


__all__ = ('current_buffer_contains', 'buffer_count_is', 'current_buffer_matches',)
