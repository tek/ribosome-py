from typing import Generator, TypeVar, Generic, Type

from lenses import Lens

from ribosome.data import Data
from ribosome import NvimFacade
from ribosome.machine.base import Machine
from ribosome.machine.transition import handle
from ribosome.machine.helpers import TransitionHelpers
from ribosome.machine.messages import UpdateRecord, UpdateState
from ribosome.machine.modular import ModularMachine, ModularMachine2
from ribosome.machine.transitions import Transitions
from ribosome.machine import trans

from amino import Maybe, Map, __, Nothing, do
from amino.state import State


T = TypeVar('T', bound=Transitions)


class ComponentMachine(Generic[T], ModularMachine2[T], TransitionHelpers):

    def __init__(self, vim: NvimFacade, trans: Type[T], name: str, parent: Maybe[Machine]) -> None:
        ModularMachine2.__init__(self, name, parent)
        self.vim = vim
        self.trans = trans

    @property
    def transitions(self) -> Type[T]:
        return self.trans

    def new_state(self):
        pass


class SubMachine(ModularMachine, TransitionHelpers):

    def new_state(self):
        pass


class SubTransitions(Transitions, TransitionHelpers):

    def _state(self, data):
        return data.sub_state(self.name, self.new_state)

    @property
    def state(self):
        return self._state(self.data)

    def _with_sub(self, data, state):
        return data.with_sub_state(self.name, state)

    def with_sub(self, state):
        return self._with_sub(self.data, state)

    @property
    def new_state(self):
        return self.machine.new_state

    @property
    def options(self):
        return getattr(self.msg, 'options', Map())

    @handle(UpdateRecord)
    def message_update_record(self):
        return (
            self.record_lens(self.msg.tpe, self.msg.name) /
            __.modify(__.update_from_opt(self.msg.options)) /
            self.with_sub
        )

    def record_lens(self, tpe, name) -> Maybe[Lens]:
        return Nothing

    @trans.unit(UpdateState, trans.st)
    @do(State[Data, None])
    def message_update_state(self) -> Generator:
        mod = __.update_from_opt(self.msg.options)
        l = yield self.state_lens(self.msg.tpe, self.msg.name)
        yield State.modify(lambda s: l.map(__.modify(mod)) | s)

    def state_lens(self, tpe: str, name: str) -> State[Data, Maybe[Lens]]:
        return State.pure(Nothing)


class Component(SubTransitions):
    pass


__all__ = ('ComponentMachine', 'SubMachine', 'SubTransitions', 'Component')
