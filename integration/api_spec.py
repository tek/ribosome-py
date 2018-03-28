from kallikrein import k, Expectation
from kallikrein.matchers import contain
from kallikrein.matchers.typed import have_type

from amino import do, Do

from ribosome.test.integration.default import ExternalSpec
from ribosome.test.klk import kn
from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.rpc import channel_id
from ribosome.nvim.api.variable import variable_set_prefixed, variable_prefixed_num


class ApiSpec(ExternalSpec):
    '''
    channel id $channel_id
    set and get a prefixed variable $set_and_get_var
    '''

    def channel_id(self) -> Expectation:
        return kn(self.vim, channel_id).must(contain(have_type(int)))

    def set_and_get_var(self) -> Expectation:
        name = 'varname'
        value = 5
        @do(NvimIO[int])
        def go() -> Do:
            yield variable_set_prefixed(name, value)
            yield variable_prefixed_num(name)
        return kn(self.vim, go).must(contain(value))


__all__ = ('ApiSpec',)
