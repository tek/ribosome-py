from amino import Map
from amino.lazy import lazy

from ribosome.data import Data
from ribosome.machine.message_base import Message
from ribosome.machine.machine import Machine
from ribosome.nvim import NvimFacade


class Transitions(Machine):
    State = Map

    def __init__(self, machine: Machine, data: Data, msg: Message) -> None:
        self.machine = machine
        self.data = data
        self.msg = msg

    @property
    def name(self):
        return self.machine.name

    @property
    def parent(self) -> Machine:
        return self.machine

    @property
    def log(self):
        return self.machine.log

    @lazy
    def local(self):
        if isinstance(self.data, Data):
            return self.data.sub_state(self.name, lambda: self._mk_state)
        else:
            return self._mk_state

    @property
    def _mk_state(self):
        return self.State()

    def with_local(self, new_data):
        return self.data.with_sub_state(self.name, new_data)

    @property
    def vim(self) -> NvimFacade:
        return self.machine.vim

__all__ = ('Transitions',)
