import sure  # NOQA

from trypnv.machine import may_handle, message
from trypnv import Machine, StateMachine

from tryp import List, Map

from unit._support.spec import Spec

M1 = message('M1')
M2 = message('M2')
M3 = message('M3')


class _A(Machine):

    @may_handle(M3)
    def m3(self, data, m):
        return data + ('c', True)

    @may_handle(M1)
    def m1(self, data, m):
        return (data + ('a', True)), M2().pub, M3()


class _B(Machine):

    @may_handle(M2)
    def m2(self, data, m):
        return data + ('b', True)


class _Z(StateMachine):

    def init(self):
        return Map()


class PublishSpec(Spec):

    def publish(self):
        Machine._data_type = Map
        z = _Z('z', List(_A('a'), _B('b')))
        res = z.send(M1())
        res.should.have.key('a').being.ok
        res.should.have.key('b').being.ok
        res.should.have.key('c').being.ok

__all__ = ['PublishSpec']
