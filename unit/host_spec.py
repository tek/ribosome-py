from typing import Tuple, Any

from kallikrein import k, Expectation

from amino.test.spec import SpecBase
from amino import List, Map, _, Right, Either, Left
from amino.state import State
from amino.lenses.lens import lens
from amino.dat import Dat

from ribosome.test.integration.run import DispatchHelper
from ribosome.request.handler.handler import RequestHandler
from ribosome.trans.api import trans
from ribosome.dispatch.component import Component, ComponentData
from ribosome.host import request_handler
from ribosome.config.config import Config
from ribosome.nvim.api.data import StrictNvimApi
from ribosome import NvimApi


class HSData(Dat['HSData']):

    def __init__(self, counter: int=1) -> None:
        self.counter = counter


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
)

extra = Component.cons(
    'extra',
    request_handlers=List(
        RequestHandler.trans_function(extra_fun)('core_fun'),
    ),
)


config = Config.cons(
    'compo',
    components=Map(core=core, extra=extra),
    core_components=List('core'),
    state_ctor=HSData,
)


class HostSpec(SpecBase):
    '''
    call multiple async transitions with the same rpc handler $multi
    '''

    def multi(self) -> Expectation:
        helper = DispatchHelper.strict(config, 'extra')
        holder = helper.holder
        as_handler = request_handler(helper.vim, False, holder)
        as_handler('function:core_fun', ((1,),))
        return k(holder.state.data.counter) == 4


__all__ = ('HostSpec',)
