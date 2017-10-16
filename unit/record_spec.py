from ribosome.record import maybe_field, field, list_field, Record, optional_field

from pyrsistent._checked_types import InvariantException

from kallikrein.matchers import equal, contain, throw
from kallikrein.matchers.typed import have_type
from kallikrein import k
from kallikrein.matchers.maybe import be_nothing

from amino import Map, List, Path


class RecA(Record):
    mand1 = field(str)
    opt = maybe_field(int)
    opt2 = optional_field(Path, factory=Path)


class RecB(RecA):
    mand2 = field(str)
    lst = list_field()


class RecordSpec:
    '''construct `Record` from a `Map` of optional values $from_opt
    '''

    def from_opt(self):
        a = 'a'
        b = 'b'
        c = 'c'
        o = 10
        o2 = 19
        o3 = '/usr/bin'
        rb = RecB.from_opt(Map(mand1=a, mand2=b, bad=1, opt=o, opt2=o3, lst=[c]))
        rb2 = rb.update_from_opt(Map(mand1=b, opt=o2))
        ra = RecA.from_opt(Map(mand1=a))
        return (
            k(rb.mand1).must(equal(a)) &
            k(rb.mand2).must(equal(b)) &
            k(rb.opt).must(contain(o)) &
            k(rb.opt2).must(contain(Path(o3))) &
            k(rb.lst).must(equal(List(c))) &
            k(rb.lst).must(have_type(List)) &
            k(rb2.mand1).must(equal(b)) &
            k(rb2.opt).must(contain(o2)) &
            k(lambda: RecB.from_opt(Map(mand1=a))).must(throw(InvariantException)) &
            k(ra.opt).must(be_nothing) &
            k(ra.mand1).must(equal(a))
        )

__all__ = ('RecordSpec',)
