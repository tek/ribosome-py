import abc
from typing import TypeVar

from ribosome.logging import Logging
from ribosome.machine.message_base import Message

from amino import Maybe, _, __


M = TypeVar('M', bound=Message)


class Machine(Logging, abc.ABC):

    @abc.abstractproperty
    def parent(self) -> Maybe['Machine']:
        ...

    @abc.abstractproperty
    def name(self) -> str:
        ...

    def bubble(self, msg: M) -> None:
        self.parent.cata(_.bubble, lambda: self.send)(msg)

    def log_message(self, msg: Message, name: str) -> None:
        return self.parent % __.log_message(msg, name)


__all__ = ('Machine',)
