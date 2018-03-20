from typing import Tuple

from kallikrein import k, Expectation
from kallikrein.matchers.length import have_length

from amino import do, Do, List
from amino.boolean import true

from ribosome.trans.api import trans
from ribosome.nvim.io import NS
from ribosome.test.integration.run import DispatchHelper
from ribosome.nvim import NvimIO
from ribosome.nvim.api import buffers, windows, Window, Buffer, current_buffer, buffer_content
from ribosome.nvim.scratch import CreateScratchBufferOptions, show_in_scratch_buffer
from ribosome.test.config import single_trans_config
from ribosome.test.integration.default import ExternalSpec


@trans.free.result(trans.st)
@do(NS[None, None])
def create_scratch(lines: List[str], options: CreateScratchBufferOptions) -> Do:
    yield NS.lift(show_in_scratch_buffer(lines, options))
    yield NS.unit


config = single_trans_config(create_scratch, json=true)


class ScratchSpec(ExternalSpec):
    '''
    launch a scratch buffer $launch
    '''

    def launch(self) -> Expectation:
        helper = DispatchHelper.nvim(config, self.vim, 'main')
        lines = List('1', '2', '3')
        @do(NvimIO[Tuple[List[Window], List[Buffer], List[str]]])
        def run() -> Do:
            yield helper.run('command:create_scratch', args=(lines, '{}',))
            wins = yield windows()
            bufs = yield buffers()
            buf = yield current_buffer()
            content = yield buffer_content(buf)
            return wins, bufs, content
        wins, bufs, content = run().unsafe(self.vim)
        return k(wins).must(have_length(2)) & k(bufs).must(have_length(2)) & (k(content) == lines)


__all__ = ('ScratchSpec',)
