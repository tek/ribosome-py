from myo.record import Record

from ribosome.record import map_field, bool_field
from ribosome.nvim.components import HasTab


class ScratchBuilder(Record):
    params = map_field()
    use_tab = bool_field()

    @property
    def tab(self):
        return self.set(use_tab=True)

    @property
    def build(self):
        return (
            (NvimIO(self._setup_tab) / self._setup_buffer)
            .map2(self._create)
        )

    def _setup_tab(self, vim):
        if self.use_tab:
            tab = vim.tabnew()
            tab.window.set_optionb('wrap', False)
            return tab
        else:
            return self.vim.tab

    def _setup_buffer(self, tab):
        buffer = tab.bufnew()
        buffer.set_options('buftype', 'nofile')
        buffer.set_options('bufhidden', 'wipe')
        buffer.set_optionb('buflisted', False)
        buffer.set_optionb('swapfile', False)
        buffer.set_modifiable(False)
        return (tab, buffer)

    def _create(self, tab, buffer):
        return ScratchBuffer(tab.vim, tab, buffer)


class ScratchBuffer(HasTab):

    def __init__(self, vim, tab, buffer):
        super().__init__(vim, buffer.target, buffer.prefix)
        self._tab = tab
        self._buffer = buffer

    @property
    def _internal_tab(self):
        return self._tab.target

    @property
    def _internal_buffer(self):
        return self._buffer.target

    def set_content(self, text):
        self._buffer.set_modifiable(True)
        self._buffer.set_content(text)
        self._buffer.set_modifiable(False)


__all__ = ('ScratchBuilder', 'ScratchBuffer')
