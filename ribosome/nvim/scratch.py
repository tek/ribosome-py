from ribosome.record import map_field, bool_field, Record, maybe_field

from amino import Empty, Just, Maybe, __
from ribosome.nvim.components import HasWindow
from ribosome.nvim import NvimIO, Tab


class ScratchBuilder(Record):
    params = map_field()
    use_tab = bool_field()
    vertical = bool_field()
    size = maybe_field(int)
    wrap = bool_field()

    @property
    def tab(self):
        return self.set(use_tab=True)

    @property
    def build(self):
        return (
            NvimIO(self._setup_window)
            .map2(self._setup_buffer)
            .map3(self._create)
        )

    def _create_window(self, vim):
        return vim.vnew() if self.vertical else vim.new()

    def _setup_window(self, vim):
        if self.use_tab:
            tab = vim.tabnew()
            return Just(tab), tab.window
        else:
            return Empty(), self._create_window(vim)

    def _setup_buffer(self, tab, win):
        win.options.set_b('wrap', self.wrap)
        buffer = win.buffer
        buffer.options.set_s('buftype', 'nofile')
        buffer.options.set_s('bufhidden', 'wipe')
        buffer.options.set_b('buflisted', False)
        buffer.options.set_b('swapfile', False)
        self.size / 'resize {}'.format % win.cmd_sync
        return (tab, win, buffer)

    def _create(self, tab, win, buffer):
        return ScratchBuffer(win.vim, tab, win, buffer)


class ScratchBuffer(HasWindow):

    def __init__(self, vim, tab: Maybe[Tab], win, buffer) -> None:
        super().__init__(vim, buffer.target, buffer.prefix)
        self._tab = tab
        self._win = win
        self._buffer = buffer

    @property
    def _internal_window(self):
        return self._win.target

    @property
    def _internal_buffer(self):
        return self._buffer.target

    def set_content(self, text):
        self._buffer.set_modifiable(True)
        self._buffer.set_content(text)
        self._buffer.set_modifiable(False)

    def close(self):
        self._tab / __.close() | self._win.close()

__all__ = ('ScratchBuilder', 'ScratchBuffer')
