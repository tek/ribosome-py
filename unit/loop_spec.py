from kallikrein import k, Expectation

from amino import Nothing, List, Just
from amino.test.spec import SpecBase

from ribosome.config import AutoData, Config

from ribosome.machine.loop import process_message
from ribosome.machine.message_base import Msg, Message
from ribosome.machine.transition import TransitionResult, handle, TransitionLog
from ribosome.machine.process_messages import PrioQueue
from ribosome.request.dispatch import PluginState
from ribosome.test.spec import MockNvimFacade
from ribosome.machine.sub import Component, ComponentMachine
from ribosome.machine.send_message import send_message


class Msg1(Msg):
    pass


class Comp1(Component):

    @handle(Msg1)
    def msg1(self) -> None:
        return Just(Msg1().pub)


class LoopSpec(SpecBase):
    '''
    test $test
    test2 $test2
    '''

    def test(self) -> Expectation:
        d = AutoData(config=Config('test'))
        a = Msg1()
        b = Msg1()
        messages = PrioQueue.empty.put_default(a).put(b, 0.1)
        def send(dat: AutoData, msg: Message) -> TransitionResult:
            return TransitionResult.empty(dat)
        result = process_message(messages, d, send)
        print(result)
        return k(1) == 1

    def test2(self) -> Expectation:
        d = AutoData(config=Config('test'))
        vim = MockNvimFacade()
        state = PluginState.cons(vim, d, None, List(ComponentMachine(vim, Comp1, 'comp1', Nothing)), PrioQueue.empty)
        a = Msg1()
        r = send_message(state, a).run(TransitionLog.empty).evaluate()
        print(r)
        return k(1) == 1


__all__ = ('LoopSpec',)
