from concurrent.futures import Future

from ribosome.machine import may_handle, pmessage, ModularMachine, Transitions
from ribosome import StateMachine
from ribosome.machine.base import MachineBase

from kallikrein import k, unsafe_k, pending
from kallikrein.matchers.maybe import be_just

from amino import List, Map

M1 = pmessage('M1')
M2 = pmessage('M2')
M3 = pmessage('M3')
M4 = pmessage('M4')
M5 = pmessage('M5', 'res')


class _A(MachineBase):

    @may_handle(M3)
    def m3(self, data, m):
        return (data + ('c', True))

    @may_handle(M1)
    def m1(self, data, m):
        return (data + ('a', True)), M2().pub, M3()


class _B(MachineBase):

    @may_handle(M2)
    def m2(self, data, m):
        return data + ('b', True), M4().pub

    @may_handle(M3)
    def m3(self, data, m):
        return data + ('c', False)


class _Z(StateMachine):

    def __init__(self, *a, **kw):
        self.goal = Future()
        super(_Z, self).__init__(*a, **kw)

    @may_handle(M4)
    def m4(self, data, m):
        self.goal.set_result(True)

    @may_handle(M5)
    def m5(self, data, m):
        self.goal.set_result(m.res)


class PublishSpec:
    '''publish a message across machines $publish
    '''

    def setup(self):
        MachineBase._data_type = Map

    @pending
    def publish(self):
        with _Z(List(_A('a'), _B('b'))).transient() as z:
            res = z.send_sync(M1())
            unsafe_k(z.goal.result()).true
        return (
            k(res.lift('a')).must(be_just(True)) &
            k(res.lift('b')).must(be_just(True)) &
            k(res.lift('c')).must(be_just(True))
        )


class _CTransitions(Transitions):

    @may_handle(M1)
    def m1(self):
        local = self.local + (self.machine.res, self.machine.res)
        return self.with_local(local), M2()


class _C(ModularMachine):
    Transitions = _CTransitions

    def __init__(self, title, res):
        self.res = res
        super().__init__(title=title)

    @may_handle(M2)
    def m2(self, data, msg):
        return data, M5(self.res).pub


class ModularSpec:
    '''publish a message from a modular machine $publish
    '''

    def publish(self):
        data = 'data'
        name = 'c'
        with _Z(List(_C(name, data))).transient() as z:
            res = z.send_sync(M1())
        return (
            (k(z.goal.result()) == data) &
            (k(res.sub_states[name][data]) == data)
        )

__all__ = ('PublishSpec', 'ModularSpec')
