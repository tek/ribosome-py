from kallikrein import k, Expectation, pending
from kallikrein.matchers.maybe import be_just

from ribosome.config.component import Component
from ribosome.config.config import Config

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


class USData(Dat['USData']):

    @staticmethod
    def cons() -> 'USData':
        return USData(D1(D2('value', items)))

    def __init__(self, d: D1) -> None:
        self.d = d


class C1Data(Dat['C1Data']):

    @staticmethod
    def cons() -> 'C1Data':
        return C1Data(D1(D2('value', items)))

    def __init__(self, d: D1) -> None:
        self.d = d


c1: Component = Component.cons('c1', state_type=C1Data)
config: Config = Config.cons('us', state_ctor=USData.cons, components=Map(c1=c1))


class UpdateStateSpec(SpecBase):
    '''
    update scalar $scalar
    update list $list
    update component state $component
    '''

    @pending
    def scalar(self) -> Expectation:
        helper = RequestHelper.strict(config)
        new = 'new'
        data = dump_json(dict(patch=dict(query='d.d', data=dict(a=new)))).get_or_raise()
        r = helper.unsafe_run_s('update_state', args=data.split(' '))
        return k(r.data.d) == D1(D2(new, items))

    @pending
    def list(self) -> Expectation:
        helper = RequestHelper.strict(config)
        new = 21
        data = dump_json(dict(patch=dict(query='d.d.items(name=second)', data=dict(value=new)))).get_or_raise()
        r = helper.unsafe_run_s('update_state', args=data.split(' '))
        return k(r.data.d) == D1(D2('value', List(Item('first', 4), Item('second', new))))

    @pending
    def component(self) -> Expectation:
        helper = RequestHelper.strict(config, 'c1').mod.state(__.update_component_data(C1Data.cons()))
        new = 'new'
        data = dump_json(dict(patch=dict(query='d.d', data=dict(a=new)))).get_or_raise()
        r = helper.unsafe_run_s('update_component_state', args=['c1'] + data.split(' '))
        return k(r.component_data.lift(C1Data) / _.d).must(be_just(D1(D2(new, items))))


__all__ = ('UpdateStateSpec',)
