from kallikrein import Expectation
from kallikrein.matchers import contain

from amino import Either, Right

from integration._support.handler import HandlerSpecPlugin
from integration._support.base import IntegrationSpecBase


class HandlerSpec(IntegrationSpecBase):
    '''typed transition handler
    test $test
    '''

    @property
    def plugin_class(self) -> Either[str, type]:
        return Right(HandlerSpecPlugin)

    def test(self) -> Expectation:
        self.vim.cmd('HandlerStart')
        self.vim.cmd_sync('Msg')
        return self._log_line(-1, contain('nothing'))

__all__ = ('HandlerSpec',)
