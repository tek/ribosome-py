from kallikrein import Expectation
from kallikrein.matchers.maybe import be_just
from kallikrein.matchers.end_with import end_with

from amino import Either, Right

from integration._support.handler import HandlerSpecPlugin
from integration._support.base import IntegrationSpecBase


class HandlerSpec(IntegrationSpecBase):
    '''typed transition handler
    nested handlers $nested
    unit handler $unit
    EitherState handler $est
    '''

    @property
    def plugin_class(self) -> Either[str, type]:
        return Right(HandlerSpecPlugin)

    def nested(self) -> Expectation:
        self.vim.cmd_once_defined('HandlerStage1')
        self.vim.cmd_sync('Msg')
        return self._log_line(-1, be_just(end_with('nothing')))

    def unit(self) -> Expectation:
        self.vim.cmd('HandlerStage1')
        self.vim.cmd_sync('Unit')
        return self._log_line(-1, be_just(end_with('unit')))

    def est(self) -> Expectation:
        self.vim.cmd('HandlerStage1')
        self.vim.cmd_sync('Est')
        return self._log_line(-1, be_just(end_with(': est')))

__all__ = ('HandlerSpec',)
