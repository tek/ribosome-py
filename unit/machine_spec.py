from time import sleep
import asyncio
from concurrent.futures import Future

import sure  # NOQA

from trypnv.machine import may_handle, message
from trypnv import Machine, StateMachine

from tryp import List, Map

from unit._support.spec import Spec

M1 = message('M1')
M2 = message('M2')
M3 = message('M3')
M4 = message('M4')


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

    def init(self):
        return Map()

    @may_handle(M4)
    def m4(self, data, m):
        self.goal.set_result(True)


class PublishSpec(Spec):

    def setup(self):
        super(PublishSpec, self).setup()
        Machine._data_type = Map

    def publish(self):
        with _Z('z', List(_A('a'), _B('b'))).transient() as z:
            res = z.send_wait(M1())
        res.should.have.key('a').being.ok
        res.should.have.key('b').being.ok
        res.should.have.key('c').being.ok

__all__ = ['PublishSpec']
