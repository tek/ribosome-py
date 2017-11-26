from amino import Map, __, List

from ribosome.plugin import Config
from ribosome.trans.message_base import pmessage
from ribosome.trans.api import trans
from ribosome.trans.messages import Stage1
from ribosome.config import RequestHandler
from ribosome.nvim import NvimIO
from ribosome.dispatch.component import Component
from ribosome.request.handler.prefix import Plain

Msg1 = pmessage('Msg1')
Msg2 = pmessage('Msg2')
val = 71


class SpecCore(Component):

    @trans.msg.unit(Stage1)
    def stage_1(self) -> None:
        pass

    @trans.msg.unit(Msg1, trans.nio)
    def msg1(self) -> NvimIO[None]:
        return NvimIO.delay(__.vars.set('msg_cmd_success', val))

    @trans.msg.unit(Msg2, trans.nio)
    def msg2(self) -> NvimIO[None]:
        return NvimIO.delay(__.vars.set('autocmd_success', val))


config = Config.cons(
    name='plug',
    components=Map(core=SpecCore),
    request_handlers=List(
        RequestHandler.msg_cmd(Msg1)('msg1', prefix=Plain()),
        RequestHandler.msg_autocmd(Msg2)('vim_resized', prefix=Plain()),
    ),
)

__all__ = ('config',)
