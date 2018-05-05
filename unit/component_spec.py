from kallikrein import k, Expectation
from kallikrein.matchers.either import be_right
from kallikrein.matchers import contain

from amino.test.spec import SpecBase
from amino import List, Map, do, Do, Dat, _
from amino.lenses.lens import lens

from ribosome.test.integration.run import RequestHelper
from ribosome.config.config import Config, NoData
from ribosome.compute.api import prog
from ribosome.config.component import Component, ComponentData
from ribosome.nvim.io.state import NS
from ribosome.config.resources import Resources
from ribosome.rpc.api import rpc


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


@prog.do
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


class ComponentSpec(SpecBase):
    '''
    enable a component $enable_component
    switch between components $switch
    '''

    def enable_component(self) -> Expectation:
        helper = RequestHelper.strict(config)
        s = helper.unsafe_run_s('enable_components', args=('extra',))
        return k(s.components.all / _.name).must(contain('extra'))

    def switch(self) -> Expectation:
        helper = RequestHelper.strict(config, 'extra')
        s, r = helper.unsafe_run('switch', args=())
        return (
            (k(r) == 17) &
            (k(s.data_by_name('core')).must(be_right(CoreData(-10)))) &
            (k(s.data_by_name('extra')).must(be_right(ExtraData(20))))
        )


__all__ = ('ComponentSpec',)
