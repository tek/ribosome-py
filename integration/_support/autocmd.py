from amino import Map, List, do, Do

from ribosome.compute.api import prog
from ribosome.config.component import Component
from ribosome.request.handler.prefix import Plain
from ribosome.request.handler.handler import RequestHandler
from ribosome.config.config import Config, NoData
from ribosome.nvim.api.variable import variable_set
from ribosome.nvim.io.state import NS

val = 71


@prog.unit
def trans1() -> NS[NoData, None]:
    return NS.lift(variable_set('autocmd_success', val))


core: Component = Component.cons('core')


config: Config = Config.cons(
    name='plug',
    components=Map(core=core),
    request_handlers=List(
        RequestHandler.trans_autocmd(trans1)('vim_resized', prefix=Plain()),
    ),
)

__all__ = ('config',)
