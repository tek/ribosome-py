from amino import Map, List
from ribosome.config import Config, RequestHandler
from ribosome.trans.message_base import Message
from ribosome.trans.messages import Stage1
from ribosome.trans.api import trans
from ribosome.dispatch.component import Component


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

    @trans.msg.unit(Stage1)
    def stage_1(self) -> None:
        pass

    @trans.msg.one(Target)
    def target(self) -> Message:
        return T1().to('q')

    @trans.msg.one(T1)
    def t1(self) -> Message:
        return T2()

    @trans.msg.multi(Seq)
    def seq(self) -> List[Message]:
        return List(S1().at(1), S2().at(0.1))


class Q(Component):

    @trans.msg.one(P1)
    def p1(self) -> Message:
        return P2()

    @trans.msg.one(T1)
    def t1(self) -> Message:
        return T3()

    @trans.msg.one(S2)
    def s1(self) -> Message:
        return S3().at(0.6)


@trans.msg.one(Pub)
def pub(msg: Pub) -> Message:
    return P1()


config = Config.cons(
    name='envl',
    components=Map(p=P, q=Q),
    request_handlers=List(
        RequestHandler.trans_cmd(pub)('pub'),
        RequestHandler.msg_cmd(Target)('target'),
        RequestHandler.msg_cmd(Seq)('Seq'),
    ),
    core_components=List('p', 'q')
)

__all__ = ('config',)
