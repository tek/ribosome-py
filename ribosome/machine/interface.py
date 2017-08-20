import abc

from ribosome.logging import Logging


class MachineI(Logging, abc.ABC):

    @abc.abstractproperty
    def title(self) -> str:
        ...


__all__ = ('MachineI',)
