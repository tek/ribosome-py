from typing import Tuple

from kallikrein import k, Expectation
from kallikrein.matchers.length import have_length

from amino import Map, do, Do, List
from amino.boolean import true

from ribosome.trans.api import trans
from ribosome.nvim.io import NS
from ribosome.dispatch.component import Component
from ribosome.request.handler.handler import RequestHandler
from ribosome.config.config import Config
from ribosome.test.integration.run import DispatchHelper
from ribosome.test.integration.klk import VimIntegrationKlkSpec
from ribosome.nvim import NvimIO
from ribosome.nvim.api import buffers, windows, Window, Buffer, current_buffer, buffer_content
from ribosome.nvim.scratch import CreateScratchBufferOptions, show_in_scratch_buffer


@trans.free.result(trans.st)
@do(NS[None, None])
def create_scratch(lines: List[str], options: CreateScratchBufferOptions) -> Do:
    yield NS.lift(show_in_scratch_buffer(lines, options))
    yield NS.unit


component = Component.cons(
    'main',
    request_handlers=List(
        RequestHandler.trans_cmd(create_scratch)(json=true),
    )
)
config = Config.cons(
    name='scratch',
    prefix='scr',
    components=Map(main=component),
)


class ScratchSpec(VimIntegrationKlkSpec):
    '''
    launch a scratch buffer $launch
    '''

    @property
    def plugin_name(self) -> str:
        return 'scratch'

    def plugin_prefix(self) -> str:
        return 'scratch'

    def launch(self) -> Expectation:
        helper = DispatchHelper.nvim(config, self.vim, 'main')
        lines = List('1', '2', '3')
        @do(NvimIO[Tuple[List[Window], List[Buffer], List[str]]])
        def run() -> Do:
            yield helper.loop('command:create_scratch', args=(lines, '{}',))
            wins = yield windows()
            bufs = yield buffers()
            buf = yield current_buffer()
            content = yield buffer_content(buf)
            return wins, bufs, content
        wins, bufs, content = run().unsafe(self.vim)
        return k(wins).must(have_length(2)) & k(bufs).must(have_length(2)) & (k(content) == lines)


__all__ = ('ScratchSpec',)
