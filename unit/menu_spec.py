from kallikrein import Expectation, k
from kallikrein.matchers.length import have_length

from amino.test.spec import SpecBase
from amino import Map, List, do, Do, Dat, Nil
from amino.logging import module_log

from ribosome.test.integration.external import external_state_test
from ribosome.config.config import Config
from ribosome.test.config import default_config_name, TestConfig
from ribosome.config.component import Component
from ribosome.rpc.api import rpc
from ribosome.compute.api import prog
from ribosome.nvim.io.state import NS
from ribosome.data.plugin_state import PS
from ribosome.test.prog import fork_request
from ribosome.util.menu.data import MenuAction, MenuContent, MenuState, MenuLine, MenuUnit
from ribosome.util.menu.run import run_menu_prog
from ribosome.nvim.api.ui import send_input, current_cursor
from ribosome.nvim.api.function import define_function
from ribosome.nvim.api.variable import var_becomes
from ribosome.util.menu.prompt.data import InputState, PromptUpdate
from ribosome.test.klk.matchers.buffer import current_buffer_matches
from ribosome.util.menu.auto.run import auto_menu
from ribosome.util.menu.auto.data import AutoUpdate

log = module_log()


class MState(Dat['MState']):

    def __init__(self) -> None:
        pass


@do(NS[InputState[MenuState[MState, None], AutoUpdate[MState, None]], MenuAction])
def handle_input(update: PromptUpdate[AutoUpdate[MState, None]]) -> Do:
    yield NS.unit
    return MenuUnit()


lines = List(
    MenuLine('first', None),
    MenuLine('second', None),
    MenuLine('third', None),
)
content = MenuContent.cons(lines, lines)
menu_state = MState()
menu = auto_menu(menu_state, content, handle_input, 'spec menu', Map())


@prog.do(None)
def spec_menu() -> Do:
    yield run_menu_prog(menu)


component: Component = Component.cons(
    'main',
    rpc=List(
        rpc.write(spec_menu),
    ),
)
config: Config = Config.cons(
    name=default_config_name,
    prefix=default_config_name,
    components=Map(main=component),
)
test_config = TestConfig.cons(config, components=List('main'))


loop_fun = '''let g:looping = 1
  while g:looping
    sleep 100m
  endwhile
'''


@do(NS[PS, Expectation])
def menu_spec() -> Do:
    yield NS.lift(define_function('Loop', Nil, loop_fun))
    yield NS.lift(send_input(':call Loop()<cr>'))
    yield fork_request('spec_menu')
    yield NS.lift(var_becomes('looping', 1))
    yield NS.lift(send_input('ir<esc>j'))
    content = yield NS.lift(current_buffer_matches(have_length(2)))
    line, col = yield NS.lift(current_cursor())
    return content & (k(line) == 2)


class MenuSpec(SpecBase):
    '''
    run a menu $menu
    '''

    def menu(self) -> Expectation:
        return external_state_test(test_config, menu_spec)


__all__ = ('MenuSpec',)
