from amino import Map, List
from ribosome.config.config import Config, RequestHandler
from ribosome.trans.message_base import Message, pmessage
from ribosome.trans.api import trans
from ribosome.dispatch.component import Component, Component

Stage1 = pmessage('Stage1')


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


@trans.msg.one(Target)
def p_target(msg: Target) -> Message:
    return T1().to('q')

@trans.msg.one(T1)
def p_t1(msg: T1) -> Message:
    return T2()

@trans.msg.multi(Seq)
def p_seq(msg: Seq) -> List[Message]:
    return List(S1().at(1), S2().at(0.1))


@trans.msg.one(P1)
def q_p1(msg: P1) -> Message:
    return P2()

@trans.msg.one(T1)
def q_t1(msg: T1) -> Message:
    return T3()

@trans.msg.one(S2)
def q_s1(msg: S2) -> Message:
    return S3().at(0.6)


@trans.free.one()
def pub() -> Message:
    return P1()


p = Component.cons('p', handlers=List(p_target, p_t1, p_seq))
q = Component.cons('q', handlers=List(q_p1, q_t1, q_s1))
config = Config.cons(
    name='envl',
    components=Map(p=p, q=q),
    request_handlers=List(
        RequestHandler.trans_cmd(pub)(),
        RequestHandler.msg_cmd(Target)(),
        RequestHandler.msg_cmd(Seq)(),
    ),
    core_components=List('p', 'q')
)

__all__ = ('config',)
