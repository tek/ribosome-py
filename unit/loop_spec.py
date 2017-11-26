from typing import Any

from kallikrein import k, Expectation
from kallikrein.matchers.maybe import be_just
from kallikrein.matchers.typed import have_type

from amino import List, Just, _
from amino.test.spec import SpecBase

from ribosome.config import AutoData, Config

from ribosome.test.spec import MockNvimFacade
from ribosome.dispatch.component import Component
from ribosome.dispatch.loop import process_message
from ribosome.trans.message_base import Msg, Message
from ribosome.trans.queue import PrioQueue
from ribosome.trans.send_message import send_message
from ribosome.plugin_state import PluginState
from ribosome.trans.api import trans
from ribosome.dispatch.data import DispatchResult, DispatchUnit
from ribosome.nvim.io import NvimIOState


class Msg1(Msg): pass


class Msg2(Msg): pass


class Comp1(Component):

    @trans.msg.one(Msg1, trans.m)
    def msg1(self) -> None:
        return Just(Msg2())


vim = MockNvimFacade()


class LoopSpec(SpecBase):
    '''
    process the lowest prio message in the queue $prio
    send a message to a component $send_message
    '''

    def prio(self) -> Expectation:
        d = AutoData(config=Config.cons('test'))
        a = Msg1()
        b = Msg2()
        messages = PrioQueue.empty.put_default(a).put(b, 0.1)
        def send(msg: Message) -> NvimIOState[Any, DispatchResult]:
            return NvimIOState.pure(DispatchResult(DispatchUnit(), msgs=List(msg)))
        (messages1, s) = process_message(messages, send)
        result = s.run_a(d).unsafe(vim)
        return k(result.msgs.head).must(be_just(b))

    def send_message(self) -> Expectation:
        d = AutoData(config=Config.cons('test'))
        state = PluginState.cons(d, None, List(Comp1('comp1')), PrioQueue.empty)
        a = Msg1()
        r = send_message(a).run_a(state).unsafe(vim)
        return k(r.output.results.head // _.msgs.head / _.msg).must(be_just(have_type(Msg2)))


__all__ = ('LoopSpec',)
