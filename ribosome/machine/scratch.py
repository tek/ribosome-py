import re
import abc
from typing import Callable

from ribosome.machine.message_base import pmessage
from ribosome.nvim import HasNvim, NvimFacade, ScratchBuffer
from ribosome.machine.base import UnitIO
from ribosome.machine.transition import may_handle, handle
from ribosome.machine.internal import KillMachine
from ribosome.dispatch.component import Component

from amino import Map, Boolean, __, Empty
from amino.io import IO

Mapping = pmessage('Mapping', 'uuid', 'keyseq')
Quit = pmessage('Quit')


class Scratch(Component, metaclass=abc.ABCMeta):

    def __init__(self, scratch: ScratchBuffer, parent=None, name=None) -> None:
        self.scratch = scratch
        Component.__init__(self, parent, name=name)
        self._create_mappings()
        self._create_autocmds()

    @abc.abstractproperty
    def prefix(self) -> str:
        ...

    @abc.abstractproperty
    def mappings(self) -> Map[str, Callable]:
        ...

    @property
    def _quit_seq(self):
        return '%%quit%%'

    @property
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
        return 'call {}Mapping(\'{}\', \'{}\')'.format(self.prefix, self.uuid, seq)

    def _create_autocmds(self):
        cmd = self.scratch.buffer.autocmd('BufWipeout', self._mapping_call(self._quit_seq))
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
        close = IO.delay(self.scratch.close)
        return UnitIO(close), KillMachine(self.uuid).pub

__all__ = ('ScratchMachine',)
