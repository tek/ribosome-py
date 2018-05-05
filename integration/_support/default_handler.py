from amino import Either, List, do, Do

from ribosome.config.config import Config, NoData
from ribosome.compute.api import prog
from ribosome.rpc.api import rpc
from ribosome.nvim.io.state import NS
from ribosome.rpc.data.prefix_style import Plain

class_name = 'ZeeKlass'


@prog
@do(NS[NoData, str])
def test_path() -> Do:
    yield NS.pure(Either.import_name('pkg', class_name).map(lambda a: a.__name__).value_or('failed'))


default_handler_spec_config: Config = Config.cons(
    'plug',
    rpc=List(
        rpc.write(test_path).conf(prefix=Plain(), sync=True),
    )
)

__all__ = ('default_handler_spec_config',)
