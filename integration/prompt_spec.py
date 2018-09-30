from kallikrein import Expectation

from chiasma.test.tmux_spec import tmux_spec_socket

from amino.test.spec import SpecBase
from amino import List, do, Do, Map, Dat
from amino.logging import module_log

from ribosome.test.integration.tmux import tmux_plugin_test, screenshot
from ribosome.config.config import Config
from ribosome.rpc.api import rpc
from ribosome.compute.api import prog
from ribosome.nvim.io.state import NS
from ribosome.test.config import TestConfig
from ribosome.nvim.io.compute import NvimIO
from ribosome.util.menu.prompt.run import prompt
from ribosome.util.menu.prompt.data import InputChar, InputState, PromptUnit
from ribosome.nvim.api.ui import send_input
from ribosome.nvim.io.api import N

log = module_log()


class PromptData(Dat['PromptData']):

    @staticmethod
    def cons(
            line: str='',
    ) -> 'PromptData':
        return PromptData(
            line,
        )

    def __init__(self, line: str) -> None:
        self.line = line


@do(NS[InputState[None, None], None])
def handle_input(keys: List[InputChar]) -> Do:
    yield NS.unit
    return PromptUnit()


@prog
@do(NS[None, None])
def write_prompt() -> Do:
    yield NS.lift(prompt(handle_input, None))
    yield NS.unit


config: Config[PromptData, None] = Config.cons(
    'prompt',
    rpc=List(rpc.write(write_prompt)),
    state_ctor=PromptData.cons,
)
vars = Map(
    prompt_tmux_socket=tmux_spec_socket,
)
test_config = TestConfig.cons(config, vars=vars)


@do(NvimIO[Expectation])
def prompt_spec() -> Do:
    yield send_input(':call PromptWritePrompt()<cr>')
    yield N.sleep(.1)
    yield send_input('a' * 5)
    yield N.sleep(.5)
    yield send_input('<c-c>')
    yield screenshot('prompt', 'simple')


class PromptSpec(SpecBase):
    '''
    write a prompt $prompt
    '''

    def prompt(self) -> Expectation:
        return tmux_plugin_test(test_config, prompt_spec)


__all__ = ('PromptSpec',)
