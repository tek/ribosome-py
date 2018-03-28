from amino import do, Do, List, Boolean, Maybe, Dat, Just, Nothing
from amino.boolean import false, true

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.ui import current_tabpage, current_window, window_buffer, set_buffer_content
from ribosome.nvim.api.data import Window, Buffer, Tabpage
from ribosome.nvim.api.option import option_buffer_set
from ribosome.nvim.api.command import nvim_command
from ribosome.nvim.io.api import N


class ScratchUi(Dat['ScratchUi']):

    def __init__(self, window: Window, tab: Maybe[Tabpage], previous: Window) -> None:
        self.window = window
        self.tab = tab
        self.previous = previous


class ScratchBuffer(Dat['ScratchBuffer']):

    def __init__(self, buffer: Buffer, ui: ScratchUi) -> None:
        self.buffer = buffer
        self.ui = ui


@do(NvimIO[Tabpage])
def create_scratch_tab() -> Do:
    yield nvim_command('tabnew')
    yield current_tabpage()


@do(NvimIO[Window])
def create_scratch_window(vertical: Boolean) -> Do:
    yield nvim_command('vnew' if vertical else 'new')
    yield current_window()


@do(NvimIO[ScratchUi])
def create_scratch_ui(use_tab: Boolean, vertical: Boolean) -> Do:
    current = yield current_window()
    tab = yield create_scratch_tab() / Just if use_tab else N.pure(Nothing)
    window = yield current_window() if use_tab else create_scratch_window(vertical)
    return ScratchUi(window, tab, current)


@do(NvimIO[None])
def configure_scratch_buffer(buffer: Buffer) -> Do:
    yield option_buffer_set(buffer, 'buftype', 'nofile')
    yield option_buffer_set(buffer, 'bufhidden', 'wipe')
    yield option_buffer_set(buffer, 'buflisted', False)
    yield option_buffer_set(buffer, 'swapfile', False)
    yield option_buffer_set(buffer, 'modifiable', False)


@do(NvimIO[Buffer])
def setup_scratch_buffer(ui: ScratchUi) -> Do:
    buffer = yield window_buffer(ui.window)
    yield configure_scratch_buffer(buffer)
    return buffer


class CreateScratchBufferOptions(Dat['CreateScratchOptions']):

    @staticmethod
    def cons(
            tab: bool=None,
            vertical: bool=None,
            size: int=None,
            wrap: bool=None,
    ) -> None:
        return CreateScratchBufferOptions(
            Maybe.optional(tab),
            Maybe.optional(vertical),
            Maybe.optional(size),
            Maybe.optional(wrap),
        )

    def __init__(self, tab: Maybe[Boolean], vertical: Maybe[Boolean], size: Maybe[int], wrap: Maybe[Boolean],) -> None:
        self.tab = tab
        self.vertical = vertical
        self.size = size
        self.wrap = wrap


@do(NvimIO[ScratchBuffer])
def create_scratch_buffer(options: CreateScratchBufferOptions) -> Do:
    ui = yield create_scratch_ui(options.tab | false, options.vertical | false)
    buffer = yield setup_scratch_buffer(ui)
    return ScratchBuffer(buffer, ui)


@do(NvimIO[None])
def set_scratch_buffer_content(scratch: ScratchBuffer, lines: List[str]) -> Do:
    yield option_buffer_set(scratch.buffer, 'modifiable', True)
    yield set_buffer_content(scratch.buffer, lines)
    yield option_buffer_set(scratch.buffer, 'modifiable', False)


@do(NvimIO[ScratchBuffer])
def show_in_scratch_buffer(lines: List[str], options: CreateScratchBufferOptions) -> Do:
    scratch = yield create_scratch_buffer(options)
    yield set_scratch_buffer_content(scratch, lines)
    return scratch


@do(NvimIO[ScratchBuffer])
def show_in_scratch_buffer_default(lines: List[str]) -> Do:
    yield show_in_scratch_buffer(lines, CreateScratchBufferOptions.cons())


__all__ = ('setup_scratch_buffer', 'CreateScratchBufferOptions', 'create_scratch_buffer', 'show_in_scratch_buffer',
           'show_in_scratch_buffer_default')
