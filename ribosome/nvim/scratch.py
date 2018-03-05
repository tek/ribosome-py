from msgpack import ExtType

from amino import do, Do, List, Boolean, Maybe, Dat, Just, Nothing
from amino.boolean import false, true

from ribosome.nvim import NvimIO
from ribosome.nvim.api import (current_tabpage, current_window, Window, Buffer, window_buffer, Tabpage,
                               set_buffer_content, set_buffer_option)


class ScratchUi(Dat['ScratchUi']):

    def __init__(self, window: ExtType, tab: Maybe[ExtType]) -> None:
        self.window = window
        self.tab = tab


class ScratchBuffer(Dat['ScratchBuffer']):

    def __init__(self, buffer: ExtType, ui: ScratchUi) -> None:
        self.buffer = buffer
        self.ui = ui


@do(NvimIO[Tabpage])
def create_scratch_tab() -> Do:
    yield NvimIO.cmd_sync('tabnew')
    yield current_tabpage()


@do(NvimIO[Window])
def create_scratch_window(vertical: Boolean) -> Do:
    yield NvimIO.cmd_sync('vnew' if vertical else 'new', True)
    yield current_window()


@do(NvimIO[ScratchUi])
def create_scratch_ui(use_tab: Boolean, vertical: Boolean) -> Do:
    tab = yield create_scratch_tab() / Just if use_tab else NvimIO.pure(Nothing)
    window = yield current_window() if use_tab else create_scratch_window(vertical)
    return ScratchUi(window, tab)


@do(NvimIO[None])
def configure_scratch_buffer(buffer: Buffer) -> Do:
    yield set_buffer_option(buffer, 'buftype', 'nofile')
    yield set_buffer_option(buffer, 'bufhidden', 'wipe')
    yield set_buffer_option(buffer, 'buflisted', False)
    yield set_buffer_option(buffer, 'swapfile', False)


@do(NvimIO[Buffer])
def setup_scratch_buffer(ui: ScratchUi) -> Do:
    buffer = yield window_buffer(ui.window)
    yield configure_scratch_buffer(buffer)
    return buffer


class CreateScratchBufferOptions(Dat['CreateScratchOptions']):

    def __init__(self, tab: Maybe[Boolean], vertical: Maybe[Boolean], size: Maybe[int], wrap: Maybe[Boolean],) -> None:
        self.tab = tab
        self.vertical = vertical
        self.size = size
        self.wrap = wrap


@do(NvimIO[ScratchBuffer])
def create_scratch_buffer(options: CreateScratchBufferOptions) -> Do:
    ui = yield create_scratch_ui(options.tab | false, options.vertical | true)
    buffer = yield setup_scratch_buffer(ui)
    return ScratchBuffer(buffer, ui)


@do(NvimIO[ScratchBuffer])
def show_in_scratch_buffer(lines: List[str], options: CreateScratchBufferOptions) -> Do:
    scratch = yield create_scratch_buffer(options)
    yield set_buffer_content(scratch.buffer, lines)
    return scratch


__all__ = ('setup_scratch_buffer', 'CreateScratchBufferOptions', 'create_scratch_buffer', 'show_in_scratch_buffer')
