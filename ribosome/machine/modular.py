import abc
import inspect
from typing import TypeVar, Generic, Type

from amino import List, L, _
from amino.lazy import lazy

from ribosome.machine.transitions import Transitions
from ribosome.machine.base import MachineBase, message_handlers, handlers
from ribosome.machine.transition import Handler
from ribosome.machine.trans import WrappedHandler

T = TypeVar('T', bound=Transitions)


def trans_handlers(cls: Type[Transitions]) -> List[Handler]:
    return handlers(cls) / L(WrappedHandler)(cls, _)


class ModularMachine(Generic[T], MachineBase):
    Transitions: Type[T] = Transitions

    @lazy
    def _message_handlers(self):
        return message_handlers(trans_handlers(self.Transitions) + handlers(type(self)))


class ModularMachine2(Generic[T], MachineBase):

    @abc.abstractproperty
    def transitions(self) -> Type[T]:
        ...

    @lazy
    def _message_handlers(self):
        return message_handlers(trans_handlers(self.transitions) + handlers(type(self)))

__all__ = ('ModularMachine',)
