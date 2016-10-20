from unit._support.spec import Spec

from ribosome.record import maybe_field, field, list_field, Record

from pyrsistent._checked_types import InvariantException

from amino import Map, List


class RecA(Record):
    mand1 = field(str)
    opt = maybe_field(int)


class RecB(RecA):
    mand2 = field(str)
    lst = list_field()


class RecordSpec(Spec):

    def from_opt(self):
        a = 'a'
        b = 'b'
        c = 'c'
        o = 10
        o2 = 19
        rb = RecB.from_opt(Map(mand1=a, mand2=b, bad=1, opt=o, lst=[c]))
        rb.mand1.should.equal(a)
        rb.mand2.should.equal(b)
        rb.opt.should.contain(o)
        rb.lst.should.equal(List(c))
        rb.lst.should.be.a(List)
        rb2 = rb.update_from_opt(Map(mand1=b, opt=o2))
        rb2.mand1.should.equal(b)
        rb2.opt.should.contain(o2)
        (RecB.from_opt
         .when.called_with(Map(mand1=a))
         .should.throw(InvariantException))
        ra = RecA.from_opt(Map(mand1=a))
        ra.opt.should.be.empty
        ra.mand1.should.equal(a)

__all__ = ('RecordSpec',)
