from amino import Either, List, do, Do

from ribosome.config.config import Config, NoData
from ribosome.compute.api import prog
from ribosome.request.handler.handler import RequestHandler
from ribosome.request.handler.prefix import Plain
from ribosome.nvim.io.state import NS

class_name = 'ZeeKlass'


@prog.result
def test_path() -> NS[NoData, str]:
    return NS.pure(Either.import_name('pkg', class_name).map(lambda a: a.__name__).value_or('failed'))


config: Config = Config.cons(
    'plug',
    request_handlers=List(
        RequestHandler.trans_function(test_path)(prefix=Plain(), sync=True),
    )
)

__all__ = ('config',)
