from kallikrein import Expectation, k
from kallikrein.matchers.either import be_right

from ribosome.test.integration.klk import AutoPluginIntegrationKlkSpec

from amino import Map, List, __
from ribosome.settings import Config, RequestHandler
from ribosome.machine.message_base import Message
from ribosome.machine.messages import Stage1
from ribosome.machine import trans
from ribosome.machine.state import Component


class Pub(Message['Pub']):
    pass


class P1(Message['P1']):
    pass


class P2(Message['P2']):
    pass


class Target(Message['Target']):
    pass


class T1(Message['T1']):
    pass


class T2(Message['T2']):
    pass


class T3(Message['T3']):
    pass


class Seq(Message['Seq']):
    pass


class S1(Message['S1']):
    pass


class S2(Message['S2']):
    pass


class S3(Message['S3']):
    pass


class P(Component):

    @trans.unit(Stage1)
    def stage_1(self) -> None:
        pass

    @trans.one(Pub)
    def pub(self) -> Message:
        return P1().pub

    @trans.one(Target)
    def target(self) -> Message:
        return T1().to('q')

    @trans.one(T1)
    def t1(self) -> Message:
        return T2()

    @trans.multi(Seq)
    def seq(self) -> List[Message]:
        return List(S1().at(1), S2().at(0.1))


class Q(Component):

    @trans.one(P1)
    def p1(self) -> Message:
        return P2()

    @trans.one(T1)
    def t1(self) -> Message:
        return T3()

    @trans.one(S2)
    def s1(self) -> Message:
        return S3().at(0.6)


config = Config(
    name='envl',
    components=Map(p=P, q=Q),
    request_handlers=List(
        RequestHandler.msg_cmd(Pub)('pub'),
        RequestHandler.msg_cmd(Target)('target'),
        RequestHandler.msg_cmd(Seq)('Seq'),
    ),
    core_components=List('p', 'q')
)


class EnvelopeSpec(AutoPluginIntegrationKlkSpec):
    '''
    publish a message $publish
    send message to specific machine $target
    process messages according to their priority values $prio
    '''

    def module(self) -> str:
        return __name__

    @property
    def plugin_prefix(self) -> str:
        return 'envl'

    def publish(self) -> Expectation:
        self.vim.cmd_once_defined('EnvlStage1')
        self.cmd_sync('EnvlPub')
        return self.seen_message(P2)

    def target(self) -> Expectation:
        self.vim.cmd_once_defined('EnvlStage1')
        self.cmd_sync('EnvlTarget')
        self.seen_message(T3)
        return self.seen_times(T2, 0)

    def prio(self) -> Expectation:
        self.vim.cmd_once_defined('EnvlStage1')
        self.cmd_sync('EnvlSeq')
        self.seen_message(S3)
        return k(self.message_log() / __.drop(2)).must(be_right(List(S2(), S3(), S1())))

__all__ = ('EnvelopeSpec', 'config')
