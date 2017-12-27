from kallikrein import k, Expectation

from amino.test.spec import SpecBase
from amino import List, Map

from ribosome.test.integration.run import DispatchHelper
from ribosome.config import Config
from ribosome.request.handler.handler import RequestHandler
from ribosome.trans.api import trans
from ribosome.trans.message_base import Msg
from ribosome.dispatch.component import Component


class TM(Msg):

    def __init__(self, i: int) -> None:
        self.i = i


@trans.msg.unit(TM)
def core_test(msg: TM) -> None:
    print('core')


@trans.msg.unit(TM)
def extra_test(msg: TM) -> None:
    print('extra')


@trans.free.unit()
def core_fun(a: int) -> None:
    print('core_fun')


@trans.free.unit()
def extra_fun(a: int) -> None:
    print('test_fun')


core = Component.cons(
    'core',
    request_handlers=List(
        RequestHandler.trans_function(core_fun)(),
    ),
    handlers=List(
        core_test,
    )
)

extra = Component.cons(
    'extra',
    request_handlers=List(
        RequestHandler.trans_function(extra_fun)(),
    ),
    handlers=List(
        extra_test,
    )
)


config = Config.cons(
    'compo',
    components=Map(core=core, extra=extra),
    core_components=List('core'),
    request_handlers=List(
        RequestHandler.msg_function(TM)('test'),
    )
)


class ComponentSpec(SpecBase):
    '''
    test $test
    enable a component $enable_component
    '''

    def test(self) -> Expectation:
        helper = DispatchHelper.cons(config)
        helper.loop('function:test', args=(5,)).unsafe(helper.vim)
        return k(1) == 1

    def enable_component(self) -> Expectation:
        helper = DispatchHelper.cons(config)
        helper.loop('command:enable_components', args=('extra',)).unsafe(helper.vim)
        return k(1) == 1


__all__ = ('ComponentSpec',)
