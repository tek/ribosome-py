from kallikrein import Expectation
from kallikrein.matchers import contain

from amino import Either, Right

from integration._support.handler import HandlerSpecPlugin
from integration._support.base import IntegrationSpecBase


class HandlerSpec(IntegrationSpecBase):
    '''typed transition handler
    nested handlers $nested
    unit handler $unit
    '''

    @property
    def plugin_class(self) -> Either[str, type]:
        return Right(HandlerSpecPlugin)

    def nested(self) -> Expectation:
        self.vim.cmd('HandlerStart')
        self.vim.cmd_sync('Msg')
        return self._log_line(-1, contain('nothing'))

    def unit(self) -> Expectation:
        self.vim.cmd('HandlerStart')
        self.vim.cmd_sync('Unit')
        return self._log_line(-1, contain('unit'))

__all__ = ('HandlerSpec',)
