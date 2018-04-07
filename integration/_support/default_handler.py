from amino import Either, List

from ribosome.config.config import Config
from ribosome.compute.api import prog
from ribosome.request.handler.handler import RequestHandler
from ribosome.request.handler.prefix import Plain

class_name = 'ZeeKlass'


@prog.result
def test_path() -> str:
    return Either.import_name('pkg', class_name).map(lambda a: a.__name__).value_or('failed')


config = Config.cons(
    'plug',
    request_handlers=List(
        RequestHandler.trans_function(test_path)(prefix=Plain(), sync=True),
    )
)

__all__ = ('config',)
