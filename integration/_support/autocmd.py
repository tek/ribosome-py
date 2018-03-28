from amino import Map, __, List

from ribosome.trans.api import trans
from ribosome.nvim.io.compute import NvimIO
from ribosome.dispatch.component import Component
from ribosome.request.handler.prefix import Plain
from ribosome.request.handler.handler import RequestHandler
from ribosome.config.config import Config
from ribosome.nvim.api.variable import variable_set

val = 71


@trans.free.unit(trans.nio)
def trans1() -> NvimIO[None]:
    return variable_set('autocmd_success', val)


core = Component.cons('core')


config = Config.cons(
    name='plug',
    components=Map(core=core),
    request_handlers=List(
        RequestHandler.trans_autocmd(trans1)('vim_resized', prefix=Plain()),
    ),
)

__all__ = ('config',)
