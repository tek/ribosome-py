from kallikrein import k, Expectation

from ribosome.test.integration.run import DispatchHelper
from ribosome.config import Config, Data

from amino.test.spec import SpecBase
from amino.dat import Dat
from amino.json import dump_json


class D2(Dat['D2']):

    def __init__(self, a: str) -> None:
        self.a = a


class D1(Dat['D1']):

    def __init__(self, d: D2) -> None:
        self.d = d


class USData(Dat['USData'], Data):

    @staticmethod
    def cons(config: Config) -> 'USData':
        return USData(config, D1(D2('value')))

    def __init__(self, config: Config, d: D1) -> None:
        self.config = config
        self.d = d


config = Config.cons('us', state_ctor=USData.cons)


class UpdateStateSpec(SpecBase):
    '''
    update state $update
    '''

    def update(self) -> Expectation:
        helper = DispatchHelper.cons(config)
        new = 'new'
        data = dump_json(dict(patch=dict(query='d.d', data=dict(a=new)))).get_or_raise()
        r = helper.loop('us:command:update_state', args=data.split(' ')).unsafe(helper.vim)
        print()
        return k(r.data.d) == D1(D2(new))

__all__ = ('UpdateStateSpec',)
