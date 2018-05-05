from kallikrein import k, Expectation

from amino.test.spec import SpecBase
from amino.test import temp_dir
from amino import Map, Dat, do, Do
from amino.lenses.lens import lens

from ribosome.nvim.api.data import StrictNvimApi
from ribosome.nvim.io.compute import NvimIO
from ribosome.util.persist import store_json_state, load_json_state
from ribosome.test.klk.matchers.nresult import nsuccess

state_dir = temp_dir('state')
vars = Map(
    ribosome_state_dir=str(state_dir),
    proteome_main_name='spec',
)
vim = StrictNvimApi.cons('persist', vars=vars)


class Counters(Dat['Counters']):

    def __init__(self, a: int, b: int) -> None:
        self.a = a
        self.b = b


class Data(Dat['Data']):

    def __init__(self, counters: Counters) -> None:
        self.counters = counters


data = Data(Counters(5, 9))


@do(NvimIO[Expectation])
def persist_spec() -> Do:
    data1 = Data(Counters(0, -17))
    yield store_json_state('counters', lambda a: a.counters).run(data)
    yield load_json_state('counters', lens.counters).run_s(data1)


class PersistSpec(SpecBase):
    '''
    store and load data as json to a file $persist
    '''

    def persist(self) -> Expectation:
        return k(persist_spec().run_a(vim)).must(nsuccess(data))


__all__ = ('PersistSpec',)
