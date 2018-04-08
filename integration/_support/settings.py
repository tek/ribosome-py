from amino import List, do, Do, _, __

from ribosome.compute.api import prog
from ribosome.request.handler.handler import RequestHandler
from ribosome.config.config import Config, NoData
from ribosome.nvim.io.state import NS
from ribosome.config.settings import Settings, int_setting
from ribosome.config.component import NoComponentData
from ribosome.config.resources import Resources


class PlugSettings(Settings):

    def __init__(self) -> None:
        super().__init__('plug')
        self.counter = int_setting('counter', 'counter', '', False)
        self.inc = int_setting('inc', 'inc', '', False)


@prog.unit
@do(NS[Resources[Settings, NoData, NoComponentData], None])
def check() -> Do:
    counter = yield NS.inspect_f(_.settings.counter.value_or_default)
    inc = yield NS.inspect_f(_.settings.inc.value_or_default)
    yield NS.inspect_f(__.settings.counter.update(counter + inc))


config: Config = Config.cons(
    name='plug',
    request_handlers=List(
        RequestHandler.trans_cmd(check)(),
    ),
    settings=PlugSettings()
)

__all__ = ('config',)
