from typing import TypeVar

from kallikrein import k, Expectation, kf

from amino.test.spec import SpecBase
from amino import List, Map, do, Do, Dat, _
from amino.state import State
from amino.lenses.lens import lens

from ribosome.config.config import Config
from ribosome.request.handler.handler import RequestHandler
from ribosome.trans.api import trans
from ribosome.dispatch.component import Component
from ribosome.trans.action import Trans
from ribosome.dispatch.execute import eval_trans
from ribosome.plugin_state import DispatchConfig, RootDispatch
from ribosome.test.integration.run import DispatchHelper
from ribosome.dispatch.run import DispatchState
from ribosome.test.klk import kn
from ribosome.nvim.io import NError

A = TypeVar('A')


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
    return a + 3


@trans.free.do()
@do(Trans)
def t2(a: int) -> Do:
    yield t2_b(a)


@trans.free.result(trans.st)
@do(State[CoreData, int])
def t3(a: int) -> Do:
    yield State.modify(lens.x.modify(_ + a))
    yield State.inspect(_.x)


@trans.free.do()
@do(Trans)
def tm() -> Do:
    a = yield t1(0)
    b = yield t2(a)
    yield t3(b)


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
helper = DispatchHelper.strict(config)
ds = DispatchState(helper.state, RootDispatch())


def run(t: Trans[A]) -> A:
    return eval_trans(t).run_a(ds).unsafe(helper.vim)


@trans.free.do()
@do(Trans[None])
def n3(a: int) -> Do:
    yield Trans.error('stop')


@trans.free.do()
@do(Trans[None])
def n2() -> Do:
    yield Trans.pure(7)


@trans.free.do()
@do(Trans[None])
def n1() -> Do:
    a = yield n2()
    b = yield n3(a)
    return b + 7


class TransSpec(SpecBase):
    '''
    nest several trans $nest
    fail on error $error
    '''

    def nest(self) -> Expectation:
        return kf(run, tm) == -7

    def error(self) -> Expectation:
        return kn(helper.vim, eval_trans.match(n1).run_a, ds) == NError('stop')


__all__ = ('TransSpec',)
