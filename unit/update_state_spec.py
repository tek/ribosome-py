from kallikrein import k, Expectation

from ribosome.test.integration.run import DispatchHelper
from ribosome.config import Config, Data

from amino.test.spec import SpecBase
from amino.dat import Dat
from amino.json import dump_json
from amino import List


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


config = Config.cons('us', state_ctor=USData.cons)


class UpdateStateSpec(SpecBase):
    '''
    update scalar $scalar
    update list $list
    '''

    def scalar(self) -> Expectation:
        helper = DispatchHelper.cons(config)
        new = 'new'
        data = dump_json(dict(patch=dict(query='d.d', data=dict(a=new)))).get_or_raise()
        r = helper.loop('us:command:update_state', args=data.split(' ')).unsafe(helper.vim)
        return k(r.data.d) == D1(D2(new, items))

    def list(self) -> Expectation:
        helper = DispatchHelper.cons(config)
        new = 21
        data = dump_json(dict(patch=dict(query='d.d.items(name=second)', data=dict(value=new)))).get_or_raise()
        r = helper.loop('us:command:update_state', args=data.split(' ')).unsafe(helper.vim)
        return k(r.data.d) == D1(D2('value', List(Item('first', 4), Item('second', new))))

__all__ = ('UpdateStateSpec',)
