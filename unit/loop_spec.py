from kallikrein import k, Expectation
from kallikrein.matchers.maybe import be_just
from kallikrein.matchers.typed import have_type

from amino import Nothing, List, Just, _
from amino.test.spec import SpecBase

from ribosome.config import AutoData, Config

from ribosome.machine.loop import process_message
from ribosome.machine.message_base import Msg, Message
from ribosome.machine.transition import TransitionResult, handle, TransitionLog
from ribosome.machine.process_messages import PrioQueue
from ribosome.dispatch import PluginState
from ribosome.test.spec import MockNvimFacade
from ribosome.dispatch.component import Component
from ribosome.machine.send_message import send_message


class Msg1(Msg): pass


class Msg2(Msg): pass


class Comp1(Component):

    @handle(Msg1)
    def msg1(self) -> None:
        return Just(Msg2().pub)


class LoopSpec(SpecBase):
    '''
    process the lowest prio message in the queue $prio
    send a message to a component $send_message
    '''

    def prio(self) -> Expectation:
        d = AutoData(config=Config('test'))
        a = Msg1()
        b = Msg2()
        messages = PrioQueue.empty.put_default(a).put(b, 0.1)
        def send(dat: AutoData, msg: Message) -> TransitionResult:
            return TransitionResult.empty(dat, output=Just(msg))
        result = process_message(messages, d, send)[1]
        return k(result.output).must(be_just(b))

    def send_message(self) -> Expectation:
        d = AutoData(config=Config('test'))
        vim = MockNvimFacade()
        state = PluginState.cons(vim, d, None, List(Comp1('comp1')), PrioQueue.empty)
        a = Msg1()
        r = send_message(state, a).run(TransitionLog.empty).evaluate()[1]
        return k(r.pub.head / _.msg).must(be_just(have_type(Msg2)))


__all__ = ('LoopSpec',)
