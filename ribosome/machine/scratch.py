import re
import abc
from typing import Callable

from ribosome.machine import message, ModularMachine, handle, may_handle
from ribosome.nvim import HasNvim, NvimFacade, ScratchBuffer
from ribosome.machine.state import KillMachine
from ribosome.machine.base import UnitTask

from amino import Map, Boolean, __, Empty
from amino.task import Task

Mapping = message('Mapping', 'uuid', 'keyseq')
Quit = message('Quit')


class ScratchMachine(ModularMachine, HasNvim, metaclass=abc.ABCMeta):

    def __init__(self, vim: NvimFacade, scratch: ScratchBuffer, parent=None,
                 title=None) -> None:
        self.scratch = scratch
        ModularMachine.__init__(self, parent, title=title)
        HasNvim.__init__(self, vim)
        self._create_mappings()

    @abc.abstractproperty
    def prefix(self) -> str:
        ...

    @abc.abstractproperty
    def mappings(self) -> Map[str, Callable]:
        ...

    def _create_mappings(self):
        self.mappings.k / self._create_mapping

    def _create_mapping(self, keyseq, to=Empty()):
        m = re.match('%(.*)%', keyseq)
        ks = '<{}>'.format(m.group(1)) if m else keyseq
        toseq = to | keyseq
        cmd = ':call {}Mapping(\'{}\', \'{}\')<cr>'
        self.scratch.buffer.nmap(ks, cmd.format(self.prefix, self.uuid, toseq))

    @handle(Mapping)
    def input(self, data, msg):
        return (
            Boolean(str(msg.uuid) == str(self.uuid))
            .flat_maybe(self.mappings.get(msg.keyseq)) /
            __()
        )

    @may_handle(Quit)
    def quit(self, data, msg):
        close = Task(self.scratch.close)
        return UnitTask(close), KillMachine(self.uuid).pub

__all__ = ('ScratchMachine',)
