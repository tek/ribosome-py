from kallikrein import k, Expectation
from kallikrein.matchers.either import be_right

from amino.test.spec import SpecBase
from amino import List, Map, do, Do, Dat, _
from amino.state import State
from amino.boolean import true
from amino.lenses.lens import lens

from ribosome.test.integration.run import DispatchHelper
from ribosome.config.config import Config, Resources, NoData
from ribosome.request.handler.handler import RequestHandler
from ribosome.trans.api import trans
from ribosome.trans.message_base import Msg
from ribosome.dispatch.component import Component, ComponentData
from ribosome.trans.action import TransM
from ribosome.config.settings import Settings


class TM(Msg):

    def __init__(self, i: int) -> None:
        self.i = i


class CoreData(Dat['CoreData']):

    @staticmethod
    def cons(x: int=-15) -> 'CoreData':
        return CoreData(x)

    def __init__(self, x: int) -> None:
        self.x = x


class ExtraData(Dat['ExtraData']):

    @staticmethod
    def cons(y: int=-19) -> 'ExtraData':
        return ExtraData(y)

    def __init__(self, y: int) -> None:
        self.y = y


@trans.msg.unit(TM)
def core_test(msg: TM) -> None:
    pass


@trans.msg.unit(TM)
def extra_test(msg: TM) -> None:
    pass


class CompoComponent(Dat['CompoComponent']):

    def __init__(self, baseline: int) -> None:
        self.baseline = baseline


@trans.free.result(trans.st, resources=true)
@do(State[Resources[Settings, ComponentData[NoData, CoreData], CompoComponent], int])
def core_fun(a: int) -> Do:
    yield State.modify(lens.data.comp.x.modify(_ + 5))
    yield State.pure(a + 5)


@trans.free.result(trans.st)
@do(State[Resources[Settings, ComponentData[NoData, CoreData], CompoComponent], int])
def extra_fun(a: int) -> Do:
    yield State.modify(lens.data.comp.y.modify(_ + 39))
    yield State.pure(a + 9)


@trans.free.do()
@do(TransM)
def switch() -> Do:
    a = yield core_fun(3).m
    yield extra_fun(a).m


core = Component.cons(
    'core',
    request_handlers=List(
        RequestHandler.trans_function(core_fun)(),
        RequestHandler.trans_function(switch)(),
    ),
    handlers=List(
        core_test,
    ),
    config=CompoComponent(13),
    state_ctor=CoreData.cons,
)

extra = Component.cons(
    'extra',
    request_handlers=List(
        RequestHandler.trans_function(extra_fun)(),
    ),
    handlers=List(
        extra_test,
    ),
    state_ctor=ExtraData.cons,
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
    enable a component $enable_component
    switch between components $switch
    '''

    def enable_component(self) -> Expectation:
        helper = DispatchHelper.cons(config)
        helper.loop('command:enable_components', args=('extra',)).unsafe(helper.vim)
        return k(1) == 1

    def switch(self) -> Expectation:
        helper = DispatchHelper.cons(config, 'extra')
        s, r = helper.unsafe_run('function:switch', args=())
        return (
            (k(r) == 17) &
            (k(s.state.data_by_name('core')).must(be_right(CoreData(-10)))) &
            (k(s.state.data_by_name('extra')).must(be_right(ExtraData(20))))
        )


__all__ = ('ComponentSpec',)
