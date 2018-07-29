from kallikrein import k, Expectation

from ribosome.nvim.io.data import NSuccess, NFatal

from amino.test.spec import SpecBase
from ribosome.test.klk.matchers.nresult import nsuccess, nfatal


class KlkSpec(SpecBase):
    '''
    success $success
    fatal $fatal
    '''

    def success(self) -> Expectation:
        return k(NSuccess(5)).must(nsuccess(5))

    def fatal(self) -> Expectation:
        x = Exception('boom')
        return k(NFatal(x)).must(nfatal(x))


__all__ = ('KlkSpec',)
