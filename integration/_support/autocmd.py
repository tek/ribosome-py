from amino import Map, __, List

from ribosome.trans.message_base import pmessage
from ribosome.trans.api import trans
from ribosome.nvim import NvimIO
from ribosome.dispatch.component import Component
from ribosome.request.handler.prefix import Plain, Full
from ribosome.request.handler.handler import RequestHandler
from ribosome.config.config import Config

Msg1 = pmessage('Msg1')
Msg2 = pmessage('Msg2')
Stage1 = pmessage('Stage1')
val = 71


@trans.msg.unit(Msg1, trans.nio)
def msg1(msg: Msg1) -> NvimIO[None]:
    return NvimIO.delay(__.vars.set('msg_cmd_success', val))


@trans.msg.unit(Msg2, trans.nio)
def msg2(msg: Msg2) -> NvimIO[None]:
    return NvimIO.delay(__.vars.set('autocmd_success', val))


core = Component.cons('core', handlers=List(msg1, msg2))


config = Config.cons(
    name='plug',
    components=Map(core=core),
    request_handlers=List(
        RequestHandler.msg_cmd(Msg1)(prefix=Plain()),
        RequestHandler.msg_cmd(Stage1)(prefix=Full()),
        RequestHandler.msg_autocmd(Msg2)('vim_resized', prefix=Plain()),
    ),
)

__all__ = ('config',)
