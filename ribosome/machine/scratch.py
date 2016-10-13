import re
import abc
from typing import Callable

from ribosome.machine import message, handle, may_handle
from ribosome.nvim import HasNvim, NvimFacade, ScratchBuffer
from ribosome.machine.state import KillMachine, SubMachine
from ribosome.machine.base import UnitTask

from amino import Map, Boolean, __, Empty
from amino.task import Task
from amino.lazy import lazy

Mapping = message('Mapping', 'uuid', 'keyseq')
Quit = message('Quit')


class ScratchMachine(SubMachine, HasNvim, metaclass=abc.ABCMeta):

    def __init__(self, vim: NvimFacade, scratch: ScratchBuffer, parent=None,
                 title=None) -> None:
        self.scratch = scratch
        SubMachine.__init__(self, parent, title=title)
        HasNvim.__init__(self, vim)
        self._create_mappings()
        self._create_autocmds()

    @abc.abstractproperty
    def prefix(self) -> str:
        ...

    @abc.abstractproperty
    def mappings(self) -> Map[str, Callable]:
        ...

    @lazy
    def _quit_seq(self):
        return '%%quit%%'

    @lazy
    def _internal_mappings(self):
        return Map({
            self._quit_seq: Quit,
        })

    def _create_mappings(self):
        self.mappings.k / self._create_mapping

    def _create_mapping(self, keyseq, to=Empty()):
        m = re.match('%(.*)%', keyseq)
        ks = '<{}>'.format(m.group(1)) if m else keyseq
        toseq = to | keyseq
        cmd = self._mapping_call(toseq)
        self.scratch.buffer.nmap(ks, ':{}<cr>'.format(cmd))

    def _mapping_call(self, seq):
        return 'call {}Mapping(\'{}\', \'{}\')'.format(self.prefix, self.uuid,
                                                       seq)

    def _create_autocmds(self):
        cmd = self.scratch.buffer.autocmd('BufWipeout',
                                          self._mapping_call(self._quit_seq))
        cmd.run_async()

    @handle(Mapping)
    def input(self, data, msg):
        return (
            Boolean(str(msg.uuid) == str(self.uuid))
            .flat_maybe(self.mappings.get(msg.keyseq))
            .or_else(self._internal_mappings.get(msg.keyseq)) /
            __()
        )

    @may_handle(Quit)
    def quit(self, data, msg):
        close = Task.delay(self.scratch.close)
        return UnitTask(close), KillMachine(self.uuid).pub

__all__ = ('ScratchMachine',)
