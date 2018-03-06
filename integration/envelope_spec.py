from kallikrein import Expectation, k, pending
from kallikrein.matchers.either import be_right

from ribosome.test.integration.klk import AutoPluginIntegrationKlkSpec

from amino import List, __

from integration._support.envelope import P1, P2, T2, T3, S1, S2, S3


class EnvelopeSpec(AutoPluginIntegrationKlkSpec):
    '''
    publish a message $publish
    send message to specific machine $target
    process messages according to their priority values $prio
    '''

    def module(self) -> str:
        return 'integration._support.envelope'

    def plugin_prefix(self) -> str:
        return 'envl'

    @pending
    def publish(self) -> Expectation:
        self.vim.cmd_once_defined('EnvlStage1')
        self.cmd_sync('EnvlPub')
        self.seen_message(P1)
        return self.seen_message(P2)

    @pending
    def target(self) -> Expectation:
        self.vim.cmd_once_defined('EnvlStage1')
        self.cmd_sync('EnvlTarget')
        self.seen_message(T3)
        return self.seen_times(T2, 0)

    @pending
    def prio(self) -> Expectation:
        self.vim.cmd_once_defined('EnvlStage1')
        self.cmd_sync('EnvlSeq')
        self.seen_message(S3)
        return k(self.message_log() / __.drop(1)).must(be_right(List(S2(), S3(), S1())))


__all__ = ('EnvelopeSpec',)
