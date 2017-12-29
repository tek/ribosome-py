from kallikrein import k, Expectation

from amino.test.spec import SpecBase
from amino import List, Map, _
from amino.state import State
from amino.lenses.lens import lens
from amino.dat import Dat

from ribosome.test.integration.run import DispatchHelper
from ribosome.request.handler.handler import RequestHandler
from ribosome.trans.api import trans
from ribosome.trans.message_base import Msg
from ribosome.dispatch.component import Component, ComponentData
from ribosome.host import request_handler
from ribosome.config.config import Config


class HSData(Dat['HSData']):

    def __init__(self, counter: int=1) -> None:
        self.counter = counter


class TM(Msg):

    def __init__(self, i: int) -> None:
        self.i = i


@trans.msg.unit(TM)
def core_test(msg: TM) -> None:
    pass


@trans.msg.unit(TM)
def extra_test(msg: TM) -> None:
    pass


@trans.free.unit(trans.st)
def core_fun(a: int) -> State[ComponentData[HSData, None], None]:
    return State.modify(lens.main.counter.modify(_ + 1))


@trans.free.unit(trans.st)
def extra_fun(a: int) -> State[ComponentData[HSData, None], None]:
    return State.modify(lens.main.counter.modify(_ + 2))


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
        RequestHandler.trans_function(extra_fun)('core_fun'),
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
    ),
    state_ctor=HSData,
)


class HostSpec(SpecBase):
    '''
    call multiple async transitions with the same rpc handler $multi
    '''

    def multi(self) -> Expectation:
        helper = DispatchHelper.cons(config, 'extra')
        as_handler = request_handler(helper.vim, False, helper.holder)
        r = as_handler('function:core_fun', ((1,),))
        return k(r.data.counter) == 4


__all__ = ('HostSpec',)
