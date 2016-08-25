from myo.record import Record

from ribosome.record import map_field, bool_field
from ribosome.nvim.components import HasWindow
from ribosome.nvim import NvimIO


class ScratchBuilder(Record):
    params = map_field()
    use_tab = bool_field()

    @property
    def tab(self):
        return self.set(use_tab=True)

    @property
    def build(self):
        return (
            (NvimIO(self._setup_window) / self._setup_buffer)
            .map2(self._create)
        )

    def _setup_window(self, vim):
        if self.use_tab:
            tab = vim.tabnew()
            return tab.window
        else:
            return vim.vnew()

    def _setup_buffer(self, win):
        win.set_optionb('wrap', False)
        buffer = win.buffer
        buffer.set_options('buftype', 'nofile')
        buffer.set_options('bufhidden', 'wipe')
        buffer.set_optionb('buflisted', False)
        buffer.set_optionb('swapfile', False)
        return (win, buffer)

    def _create(self, win, buffer):
        return ScratchBuffer(win.vim, win, buffer)


class ScratchBuffer(HasWindow):

    def __init__(self, vim, win, buffer):
        super().__init__(vim, buffer.target, buffer.prefix)
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


__all__ = ('ScratchBuilder', 'ScratchBuffer')
