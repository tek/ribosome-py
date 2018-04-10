from typing import Tuple

from kallikrein import k, Expectation
from kallikrein.matchers.length import have_length

from amino import do, Do, List
from amino.boolean import true

from ribosome.compute.api import prog
from ribosome.nvim.io.state import NS
from ribosome.test.integration.run import RequestHelper
from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.scratch import CreateScratchBufferOptions, show_in_scratch_buffer
from ribosome.test.config import single_trans_config
from ribosome.test.integration.default import ExternalSpec
from ribosome.nvim.api.ui import buffer_content, buffers, windows, current_buffer
from ribosome.nvim.api.data import Window, Buffer
from ribosome.config.config import NoData


@prog.result
@do(NS[NoData, None])
def create_scratch(lines: List[str], options: CreateScratchBufferOptions) -> Do:
    yield NS.lift(show_in_scratch_buffer(lines, options))
    yield NS.unit


config = single_trans_config(create_scratch, json=true)


class ScratchSpec(ExternalSpec):
    '''
    launch a scratch buffer $launch
    '''

    def launch(self) -> Expectation:
        helper = RequestHelper.nvim(config, self.vim, 'main')
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
