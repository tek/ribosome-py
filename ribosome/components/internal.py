from typing import TypeVar

from amino import Maybe, __, _

from ribosome.trans.messages import Nop
from ribosome.trans.api import trans
from ribosome.dispatch.component import Component
from ribosome.trans.message_base import pmessage, json_pmessage, ToMachine

Callback = pmessage('Callback', 'func')
EnvelopeOld = pmessage('EnvelopeOld', 'message', 'to')
RunMachine = json_pmessage('RunMachine', 'machine')
KillMachine = pmessage('KillMachine', 'uuid')
RunScratchMachine = json_pmessage('RunScratchMachine', 'machine')
Init = pmessage('Init')
IfUnhandled = pmessage('IfUnhandled', 'msg', 'unhandled')
A = TypeVar('A')
D = TypeVar('D')


class InternalC(Component):

    @trans.msg.unit(Nop)
    def _nop(self):
        pass

    @trans.msg.unit(Callback)
    def message_callback(self):
        return self.msg.func(self.data)

    @trans.msg.unit(RunMachine)
    def message_run_machine(self):
        self.sub = self.sub.cat(self.msg.machine)
        init = self.msg.options.get('init') | Init()
        return EnvelopeOld(init, self.msg.machine.uuid)

    @trans.msg.unit(KillMachine)
    def message_kill_machine(self):
        self.sub = self.sub.filter_not(_.uuid == self.msg.uuid)

    @trans.msg.unit(EnvelopeOld)
    def message_envelope(self):
        return self.sub.find(_.uuid == self.msg.to) / __.loop_process(self.data, self.msg.message)

    @trans.msg.unit(ToMachine)
    def message_to_machine(self) -> Maybe:
        return self.sub.find(_.name == self.msg.target) / __.loop_process(self.data, self.msg.message)

    @trans.msg.unit(IfUnhandled)
    def if_unhandled(self):
        result = self._send(self.data, self.msg.msg)
        return result if result.handled else self._send(self.data, self.msg.unhandled)

__all__ = ('InternalC', 'RunMachine', 'KillMachine', 'RunScratchMachine')
