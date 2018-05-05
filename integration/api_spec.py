from kallikrein import k, Expectation, pending
from kallikrein.matchers import contain
from kallikrein.matchers.typed import have_type

from amino import do, Do
from amino.test.spec import SpecBase

from ribosome.test.klk.expectable import kn
from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.rpc import channel_id
from ribosome.nvim.api.variable import variable_set_prefixed, variable_prefixed_num


# FIXME
class ApiSpec(SpecBase):
    '''
    channel id $channel_id
    set and get a prefixed variable $set_and_get_var
    '''

    @pending
    def channel_id(self) -> Expectation:
        return kn(self.vim, channel_id).must(contain(have_type(int)))

    @pending
    def set_and_get_var(self) -> Expectation:
        name = 'varname'
        value = 5
        @do(NvimIO[int])
        def go() -> Do:
            yield variable_set_prefixed(name, value)
            yield variable_prefixed_num(name)
        return kn(self.vim, go).must(contain(value))


__all__ = ('ApiSpec',)
