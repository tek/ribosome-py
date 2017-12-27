from kallikrein import k, Expectation
from kallikrein.matchers.maybe import be_just

from ribosome.test.integration.run import DispatchHelper
from ribosome.config import Config, Data
from ribosome.dispatch.component import Component

from amino.test.spec import SpecBase
from amino.dat import Dat
from amino.json import dump_json
from amino import List, Map, _, __


class Item(Dat['Item']):

    def __init__(self, name: str, value: int) -> None:
        self.name = name
        self.value = value


class D2(Dat['D2']):

    def __init__(self, a: str, items: List[Item]) -> None:
        self.a = a
        self.items = items


class D1(Dat['D1']):

    def __init__(self, d: D2) -> None:
        self.d = d


items = List(Item('first', 4), Item('second', 7))


class USData(Dat['USData'], Data):

    @staticmethod
    def cons(config: Config) -> 'USData':
        return USData(config, D1(D2('value', items)))

    def __init__(self, config: Config, d: D1) -> None:
        self.config = config
        self.d = d


class C1Data(Dat['C1Data'], Data):

    @staticmethod
    def cons() -> 'C1Data':
        return C1Data(D1(D2('value', items)))

    def __init__(self, d: D1) -> None:
        self.d = d


c1 = Component.cons('c1', state_ctor=C1Data.cons)


config = Config.cons('us', state_ctor=USData.cons, components=Map(c1=c1))


class UpdateStateSpec(SpecBase):
    '''
    update scalar $scalar
    update list $list
    update component state $component
    '''

    def scalar(self) -> Expectation:
        helper = DispatchHelper.cons(config)
        new = 'new'
        data = dump_json(dict(patch=dict(query='d.d', data=dict(a=new)))).get_or_raise()
        r = helper.loop('command:update_state', args=data.split(' ')).unsafe(helper.vim)
        return k(r.data.d) == D1(D2(new, items))

    def list(self) -> Expectation:
        helper = DispatchHelper.cons(config)
        new = 21
        data = dump_json(dict(patch=dict(query='d.d.items(name=second)', data=dict(value=new)))).get_or_raise()
        r = helper.loop('command:update_state', args=data.split(' ')).unsafe(helper.vim)
        return k(r.data.d) == D1(D2('value', List(Item('first', 4), Item('second', new))))

    def component(self) -> Expectation:
        helper = DispatchHelper.cons(config, 'c1').mod.state(__.update_component_data('c1', C1Data.cons()))
        new = 'new'
        data = dump_json(dict(patch=dict(query='d.d', data=dict(a=new)))).get_or_raise()
        r = helper.loop('command:update_component_state', args=['c1'] + data.split(' ')).unsafe(helper.vim)
        return k(r.component_data.lift('c1') / _.d).must(be_just(D1(D2(new, items))))

__all__ = ('UpdateStateSpec',)
