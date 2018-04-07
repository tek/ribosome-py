from typing import TypeVar

from kallikrein import Expectation, kf, k
from kallikrein.matchers import contain, equal
from kallikrein.matchers.tuple import tupled
from kallikrein.matchers.either import be_right
from kallikrein.matchers.match_with import match_with

from amino.test.spec import SpecBase
from amino import List, Map, do, Do, Dat, _, Nil, __
from amino.state import State
from amino.lenses.lens import lens

from ribosome.config.config import Config, Resources
from ribosome.dispatch.component import Component, ComponentData
from ribosome.trans.action import Prog
from ribosome.plugin_state import DispatchConfig
from ribosome.test.integration.run import DispatchHelper
from ribosome.nvim.io.data import NError
from ribosome.nvim.io.state import NS
from ribosome.config.settings import Settings
from ribosome.compute.api import prog
from ribosome.request.handler.handler import RequestHandler
from ribosome.compute.run import run_prog
from ribosome.test.klk import kn

A = TypeVar('A')


class Compon(Dat['Compon']):
    pass


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


@prog.result
@do(State[ComponentData[CoreData, ExtraData], int])
def t1(a: int) -> Do:
    yield State.modify(lens.comp.y.modify(_ + 5))
    return a + 2


@prog.result
@do(State[ComponentData[CoreData, ExtraData], int])
def t2_b(a: int) -> Do:
    yield State.inspect(_.comp.y + a + 39)


@prog.do
@do(Prog)
def t2(a: int) -> Do:
    yield t2_b(a)


@prog.result
@do(State[CoreData, int])
def t3(a: int) -> Do:
    yield State.modify(lens.x.modify(_ + a))
    return a


@prog.do
@do(Prog)
def tm() -> Do:
    a = yield t1(0)
    b = yield t2(a)
    yield t3(b)


c1: Component = Component.cons(
    'c1',
    request_handlers=List(
        RequestHandler.trans_function(t1)(),
    ),
    config=CompoComponent(13),
    state_ctor=ExtraData.cons,
    state_type=ExtraData,
)

c2: Component = Component.cons(
    'c2',
    request_handlers=List(
        RequestHandler.trans_function(t2)(),
        RequestHandler.trans_function(t2_b)(),
    ),
    state_ctor=ExtraData.cons,
    state_type=ExtraData,
)


config: Config = Config.cons(
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


@prog.do
@do(Prog[None])
def n3(a: int) -> Do:
    yield Prog.error('stop')


@prog.do
@do(Prog[None])
def n2() -> Do:
    yield Prog.pure(7)


@prog.do
@do(Prog[None])
def n1() -> Do:
    a = yield n2()
    b = yield n3(a)
    return b + 7


@prog.result
@do(NS[Resources[Settings, ComponentData[CoreData, ExtraData], Compon], str])
def comp_res() -> Do:
    s = yield NS.inspect(_.components)
    comp = yield NS.from_either(s.by_type(ExtraData))
    yield NS.modify(lens.data.comp.y.set(29))
    return comp.name


@prog.result
@do(NS[CoreData, None])
def root() -> Do:
    yield NS.pure(13)


def run_a(t: Prog[A]) -> A:
    return kn(helper.vim, lambda: run_prog(t, Nil).run_a(helper.state))


def run(t: Prog[A]) -> A:
    return kn(helper.vim, lambda: run_prog(t, Nil).run(helper.state))


class ProgSpec(SpecBase):
    '''
    nest several trans $nest
    fail on error $error
    component with resources $comp_res
    root without extras $root
    '''

    def nest(self) -> Expectation:
        return run_a(tm).must(contain(27))

    def error(self) -> Expectation:
        return run_a(n1) == NError('stop')

    def comp_res(self) -> Expectation:
        def state_updated(a) -> Expectation:
            return k(a.data_by_name(c1.name) / _.y).must(be_right(29))
        return run(comp_res).must((contain(tupled(2)((match_with(state_updated), equal(c1.name))))))

    def root(self) -> Expectation:
        return run_a(root).must(contain(13))


__all__ = ('ProgSpec',)
