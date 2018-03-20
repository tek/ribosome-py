from kallikrein import k, Expectation

from amino.test.spec import SpecBase
from amino import List, Map, do, Do, Dat, _
from amino.state import State
from amino.lenses.lens import lens

from ribosome.config.config import Config
from ribosome.request.handler.handler import RequestHandler
from ribosome.trans.api import trans
from ribosome.dispatch.component import Component
from ribosome.trans.action import Trans
from ribosome.dispatch.execute import run_trans_m
from ribosome.plugin_state import DispatchConfig, RootDispatch
from ribosome.test.integration.run import DispatchHelper
from ribosome.dispatch.run import DispatchState


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


class CompoComponent(Dat['CompoComponent']):

    def __init__(self, baseline: int) -> None:
        self.baseline = baseline


@trans.free.result(trans.st)
@do(State[ExtraData, int])
def t1(a: int) -> Do:
    yield State.modify(lens.comp.y.modify(_ + 5))
    yield State.pure(a + 5)


@trans.free.result(trans.st)
@do(State[ExtraData, int])
def t2_b(a: int) -> Do:
    yield State.modify(lens.comp.y.modify(_ + 39))


@trans.free.do()
@do(Trans)
def t2(a: int) -> Do:
    yield t2_b(a)


@trans.free.result(trans.st)
@do(State[CoreData, int])
def t3(a: int) -> Do:
    yield State.modify(lens.x.modify(_ + 39))
    yield State.inspect(_.x)


@trans.free.do()
@do(Trans)
def tm() -> Do:
    yield t1(0)
    yield t2(0)
    yield t3(0)


c1 = Component.cons(
    'c1',
    request_handlers=List(
        RequestHandler.trans_function(t1)(),
    ),
    config=CompoComponent(13),
    state_ctor=ExtraData.cons,
)

c2 = Component.cons(
    'c2',
    request_handlers=List(
        RequestHandler.trans_function(t2)(),
        RequestHandler.trans_function(t2_b)(),
    ),
    state_ctor=ExtraData.cons,
)


config = Config.cons(
    'compo',
    components=Map(c1=c1, c2=c2),
    core_components=List('c1', 'c2'),
    state_ctor=CoreData.cons,
    request_handlers=List(
        RequestHandler.trans_function(tm)(),
        RequestHandler.trans_function(t3)(),
    ),
)
dispatch_conf = DispatchConfig.cons(config)


class TransMSpec(SpecBase):
    '''
    test $test
    '''

    def test(self) -> Expectation:
        helper = DispatchHelper.cons(config)
        ds = DispatchState(helper.state, RootDispatch())
        a = run_trans_m(tm.fun()).run_a(ds).unsafe(helper.vim)
        return k(a) == 24


__all__ = ('TransMSpec',)
