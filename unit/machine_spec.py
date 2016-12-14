from concurrent.futures import Future

from ribosome.machine import may_handle, message, ModularMachine, Transitions
from ribosome import Machine, StateMachine

from amino import List, Map

from unit._support.spec import Spec

M1 = message('M1')
M2 = message('M2')
M3 = message('M3')
M4 = message('M4')
M5 = message('M5', 'res')


class _A(Machine):

    @may_handle(M3)
    def m3(self, data, m):
        return (data + ('c', True))

    @may_handle(M1)
    def m1(self, data, m):
        return (data + ('a', True)), M2().pub, M3()


class _B(Machine):

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


class PublishSpec(Spec):

    def setup(self):
        super().setup()
        Machine._data_type = Map

    def publish(self):
        with _Z(List(_A('a'), _B('b'))).transient() as z:
            res = z.send_sync(M1())
            z.goal.result().should.be.ok
        res.should.have.key('a').being.ok
        res.should.have.key('b').being.ok
        res.should.have.key('c').being.ok


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


class ModularSpec(Spec):

    def publish(self):
        data = 'data'
        name = 'c'
        with _Z(List(_C(name, data))).transient() as z:
            res = z.send_sync(M1())
            z.goal.result().should.equal(data)
            res.sub_states[name][data].should.equal(data)

__all__ = ('PublishSpec', 'ModularSpec')
