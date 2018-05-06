from typing import Tuple

from kallikrein import k, Expectation
from kallikrein.matchers.length import have_length
from kallikrein.matchers.lines import have_lines
from kallikrein.matchers.tuple import tupled

from amino import do, Do, List
from amino.boolean import true
from amino.test.spec import SpecBase

from ribosome.compute.api import prog
from ribosome.nvim.io.state import NS
from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.scratch import CreateScratchBufferOptions, show_in_scratch_buffer
from ribosome.test.config import single_trans_config
from ribosome.nvim.api.ui import buffer_content, buffers, windows, current_buffer
from ribosome.nvim.api.data import Window, Buffer
from ribosome.config.config import NoData
from ribosome.test.integration.embed import TestConfig
from ribosome.test.integration.external import request, external_state_test
from ribosome.data.plugin_state import PS


@prog.result
@do(NS[NoData, None])
def create_scratch(lines: List[str], options: CreateScratchBufferOptions) -> Do:
    yield NS.lift(show_in_scratch_buffer(lines, options))
    yield NS.unit


config = single_trans_config(create_scratch, json=true)
test_config = TestConfig.cons(config, components=List('main'))
lines = List('1', '2', '3')


@do(NvimIO[Tuple[List[Window], List[Buffer], List[str]]])
def ui_data() -> Do:
    wins = yield windows()
    bufs = yield buffers()
    buf = yield current_buffer()
    content = yield buffer_content(buf)
    return wins, bufs, content


@do(NS[PS, Expectation])
def launch_spec() -> Do:
    yield request('create_scratch', lines, '{}')
    data = yield NS.lift(ui_data())
    return k(data).must(tupled(3)((have_length(2), have_length(2), have_lines(lines))))


class ScratchSpec(SpecBase):
    '''
    launch a scratch buffer $launch
    '''

    def launch(self) -> Expectation:
        return external_state_test(test_config, launch_spec)


__all__ = ('ScratchSpec',)
