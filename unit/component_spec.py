from kallikrein import k, Expectation
from kallikrein.matchers.either import be_right
from kallikrein.matchers import contain

from amino.test.spec import SpecBase
from amino import List, Map, do, Do, Dat, _
from amino.lenses.lens import lens

from ribosome.config.config import Config, NoData
from ribosome.compute.api import prog
from ribosome.config.component import Component, ComponentData
from ribosome.nvim.io.state import NS
from ribosome.config.resources import Resources
from ribosome.rpc.api import rpc
from ribosome.test.config import TestConfig
from ribosome.test.prog import request
from ribosome.test.integration.embed import plugin_test
from ribosome.test.unit import unit_test


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
@do(NS[Resources[ComponentData[NoData, CoreData], CompoComponent], int])
def core_fun(a: int) -> Do:
    yield NS.modify(lens.data.comp.x.modify(_ + 5))
    yield NS.pure(a + 5)


@prog.result
@do(NS[Resources[ComponentData[NoData, ExtraData], CompoComponent], int])
def extra_fun(a: int) -> Do:
    yield NS.modify(lens.data.comp.y.modify(_ + 39))
    yield NS.pure(a + 9)


@prog.do(None)
def switch() -> Do:
    a = yield core_fun(3)
    yield extra_fun(a)


core = Component.cons(
    'core',
    rpc=List(
        rpc.write(core_fun),
        rpc.write(switch),
    ),
    config=CompoComponent(13),
    state_type=CoreData,
)

extra = Component.cons(
    'extra',
    rpc=List(
        rpc.write(extra_fun),
    ),
    state_type=ExtraData,
)


config = Config.cons(
    'compo',
    components=Map(core=core, extra=extra),
    core_components=List('core'),
)
test_config = TestConfig.cons(config)


@do(NS[CoreData, Expectation])
def enable_component_spec() -> Do:
    yield request('enable_components', 'extra')
    names = yield NS.inspect(lambda s: s.components.all / _.name)
    return k(names).must(contain('extra'))


@do(NS[CoreData, Expectation])
def switch_spec() -> Do:
    r = yield request('switch')
    core_data = yield NS.inspect(lambda s: s.data_by_name('core'))
    extra_data = yield NS.inspect(lambda s: s.data_by_name('extra'))
    return (
        (k(r) == List(17)) &
        (k(core_data).must(be_right(CoreData(-10)))) &
        (k(extra_data).must(be_right(ExtraData(20))))
    )


class ComponentSpec(SpecBase):
    '''
    enable a component $enable_component
    switch between components $switch
    '''

    def enable_component(self) -> Expectation:
        return unit_test(test_config, enable_component_spec)

    def switch(self) -> Expectation:
        return unit_test(TestConfig.cons(config, components=List('extra')), switch_spec)


__all__ = ('ComponentSpec',)
