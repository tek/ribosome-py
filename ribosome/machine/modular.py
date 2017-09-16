import abc
import inspect
from typing import TypeVar, Generic, Type

from amino import List, L, _

from ribosome.machine.transitions import Transitions
from ribosome.machine.base import MachineBase
from ribosome.machine.transition import WrappedHandler
from ribosome.machine.message_base import _machine_attr

T = TypeVar('T', bound=Transitions)


class ModularMachine(Generic[T], MachineBase):
    Transitions: Type[T] = Transitions

    @property
    def _handlers(self):
        methods = inspect.getmembers(self.Transitions, lambda a: hasattr(a, _machine_attr))
        handlers = (
            List.wrap(methods)
            .map2(L(WrappedHandler.create)(self, _, _, self.Transitions))
        )
        return handlers + super()._handlers


class ModularMachine2(Generic[T], MachineBase):

    @abc.abstractproperty
    def transitions(self) -> Type[T]:
        ...

    @property
    def _handlers(self):
        methods = inspect.getmembers(self.transitions, lambda a: hasattr(a, _machine_attr))
        handlers = (
            List.wrap(methods)
            .map2(L(WrappedHandler.create)(self, _, _, self.transitions))
        )
        return handlers + super()._handlers

__all__ = ('ModularMachine',)
