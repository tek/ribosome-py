import abc
import uuid
from typing import Callable

from ribosome.machine import message, ModularMachine, handle
from ribosome.nvim import HasNvim, NvimFacade, ScratchBuffer

from amino import Map, Boolean, __


Mapping = message('Mapping', 'uuid', 'keyseq')


class ScratchMachine(ModularMachine, HasNvim, metaclass=abc.ABCMeta):

    def __init__(self, vim: NvimFacade, scratch: ScratchBuffer, parent=None,
                 title=None) -> None:
        self.scratch = scratch
        self.uuid = uuid.uuid4()
        ModularMachine.__init__(self, parent, title=title)
        HasNvim.__init__(self, vim)

    @abc.abstractproperty
    def mappings(self) -> Map[str, Callable]:
        ...

    @handle(Mapping)
    def input(self, data, msg):
        return (
            Boolean(msg.uuid == self.uuid)
            .flat_maybe(self.mappings.get(msg.keyseq)) /
            __()
        )

__all__ = ('ScratchMachine',)
