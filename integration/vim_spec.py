from amino import Right, List, __, Map

from ribosome.test.integration.klk import later

from kallikrein import kf, k, Expectation
from kallikrein.matchers.either import be_right, be_left
from kallikrein.matchers.maybe import be_just

from integration._support.facade import FacadeTestPlugin
from integration._support.base import IntegrationSpecBase


class VimSpec(IntegrationSpecBase):
    '''NvimFacade
    get and set variables $vars
    '''

    @property
    def _prefix(self):
        return 'ribosome'

    @property
    def plugin_class(self):
        return Right(FacadeTestPlugin)

    def vars(self) -> Expectation:
        vname = List.random_string()
        content = [List.random_string()]
        self.vim.cmd_once_defined('Go')
        self.vim.buffer.vars.set_p(vname, content)
        later(kf(self.vim.buffer.vars.pl, vname).must(be_right(content)))
        var = (
            self.vim.call('AllVars') /
            Map //
            __.get('b:{}_{}'.format(self._prefix, vname))
        )
        return (
            k(var).must(be_just(str(content))) &
            kf(self.vim.vars.p, vname).must(be_left)
        )

__all__ = ('VimSpec',)
