from typing import Tuple

import msgpack

from amino import List, I, do, Do, Path
from amino.logging import module_log

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.data import Tabpage, Window, Buffer
from ribosome.nvim.api.util import cons_ext, cons_ext_list, cons_checked_list, cons_checked_e, extract_int_pair
from ribosome.nvim.api.command import nvim_command
from ribosome.nvim.io.api import N

log = module_log()


def current_tabpage() -> NvimIO[Tabpage]:
    return N.read_tpe('nvim_get_current_tabpage', cons_ext(Tabpage))


def current_window() -> NvimIO[Window]:
    return N.read_cons('nvim_get_current_win', cons_ext(Window))


def current_buffer() -> NvimIO[Buffer]:
    return N.read_cons('nvim_get_current_buf', cons_ext(Buffer))


def tabpages() -> NvimIO[List[Tabpage]]:
    return N.read_cons('nvim_list_bufs', cons_ext_list(Tabpage))


def windows() -> NvimIO[List[Window]]:
    return N.read_cons('nvim_list_wins', cons_ext_list(Window))


def buffers() -> NvimIO[List[Buffer]]:
    return N.read_cons('nvim_list_bufs', cons_ext_list(Buffer))


def window_buffer(window: Window) -> NvimIO[Buffer]:
    return N.read_cons('nvim_win_get_buf', cons_ext(Buffer), window.data)


def set_buffer_lines(
        buffer: Buffer,
        start: int,
        end: int,
        lines: List[str],
        strict_indexing: bool=False,
) -> NvimIO[None]:
    return N.write('nvim_buf_set_lines', buffer.data, start, end, strict_indexing, lines)


def set_buffer_content(buffer: Buffer, lines: List[str]) -> NvimIO[None]:
    return set_buffer_lines(buffer, 0, -1, lines, False)


def buffer_lines(
        buffer: Buffer,
        start: int,
        end: int,
        strict_indexing: bool=False,
) -> NvimIO[None]:
    return N.read_cons(
        'nvim_buf_get_lines',
        cons_checked_list(str, I),
        buffer.data,
        start,
        end,
        strict_indexing,
    )


def buffer_content(buffer: Buffer) -> NvimIO[List[str]]:
    return buffer_lines(buffer, 0, -1, False)


@do(NvimIO[List[str]])
def current_buffer_content() -> Do:
    buffer = yield current_buffer()
    yield buffer_content(buffer)


def buffer_number(buffer: Buffer) -> NvimIO[int]:
    return N.read_tpe('nvim_buf_get_number', int, buffer.data)


@do(NvimIO[None])
def close_buffer(buffer: Buffer) -> Do:
    yield N.pure(None)
    num = yield buffer_number(buffer)
    yield nvim_command('bdelete', num)


@do(NvimIO[None])
def close_current_buffer() -> Do:
    buffer = yield current_buffer()
    yield close_buffer(buffer)


def cursor(window: Window) -> NvimIO[Tuple[int, int]]:
    return N.read_cons('nvim_win_get_cursor', cons_checked_e(list, extract_int_pair), window.data)


@do(NvimIO[Tuple[int, int]])
def current_cursor() -> Do:
    window = yield current_window()
    yield cursor(window)


@do(NvimIO[int])
def window_line(window: Window) -> Do:
    line, col = yield cursor(window)
    return line


def focus_window(window: Window) -> NvimIO[None]:
    return N.write('nvim_set_current_win', window.data)


def buffer_name(buffer: Buffer) -> NvimIO[str]:
    return N.read_tpe('nvim_buf_get_name', str, buffer.data)


@do(NvimIO[str])
def window_buffer_name(window: Window) -> Do:
    buffer = yield window_buffer(window)
    yield buffer_name(buffer)


@do(NvimIO[str])
def current_buffer_name() -> Do:
    buffer = yield current_buffer()
    yield buffer_name(buffer)


def set_cursor(window: Window, coords: Tuple[int, int]) -> NvimIO[None]:
    line, col = coords
    return N.write('nvim_win_set_cursor', window.data, coords)


def set_line(window: Window, line: int) -> NvimIO[None]:
    return set_cursor(window, (line, 0))


@do(NvimIO[None])
def set_local_cursor(coords: Tuple[int, int]) -> Do:
    window = yield current_window()
    yield set_cursor(window, coords)


def window_number(window: Window) -> NvimIO[int]:
    return N.read_tpe('nvim_win_get_number', int, window.data)


@do(NvimIO[int])
def current_window_number() -> Do:
    window = yield current_window()
    yield window_number(window)


def send_input(data: str) -> NvimIO[None]:
    return N.write('nvim_input', data)


def edit_file(file: Path) -> NvimIO[None]:
    return nvim_command('edit', str(file))


@do(NvimIO[None])
def echo(text: str) -> Do:
    yield N.write('nvim_out_write', f"{text}\n")


def window_height(window: Window) -> NvimIO[int]:
    return N.read_tpe('nvim_win_get_height', int, window.data)


@do(NvimIO[int])
def current_window_height() -> Do:
    window = yield current_window()
    yield window_height(window)


__all__ = ('current_tabpage', 'current_window', 'current_buffer', 'tabpages', 'windows', 'buffers', 'window_buffer',
           'set_buffer_lines', 'set_buffer_content', 'buffer_lines', 'buffer_content', 'current_buffer_content',
           'buffer_number', 'close_buffer', 'close_current_buffer', 'cursor', 'current_cursor', 'window_line',
           'focus_window', 'buffer_name', 'window_buffer_name', 'current_buffer_name', 'set_cursor', 'set_line',
           'set_local_cursor', 'current_window_number', 'send_input', 'edit_file', 'echo', 'window_number',
           'window_height', 'current_window_height',)
