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
from ribosome.util.menu.data import MenuAction, MenuContent, MenuState, MenuLine, MenuUnit, MenuConfig
from ribosome.util.menu.run import run_menu_prog
from ribosome.nvim.api.ui import send_input, current_cursor
from ribosome.nvim.api.function import define_function
from ribosome.nvim.api.variable import var_becomes
from ribosome.util.menu.prompt.data import InputState, PromptUpdate
from ribosome.test.klk.matchers.buffer import current_buffer_matches
from ribosome.util.menu.auto.run import auto_menu
from ribosome.util.menu.auto.data import AutoUpdate
from ribosome.test.klk.matchers.window import current_cursor_is

log = module_log()


class MState(Dat['MState']):

    def __init__(self) -> None:
        pass


lines = List(
    MenuLine.cons('first', None),
    MenuLine.cons('second', None),
    MenuLine.cons('third', None),
)
menu_state = MState()
menu = auto_menu(menu_state, lines, MenuConfig.cons('spec menu', False))


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
    yield NS.lift(send_input('ir<esc>'))
    yield NS.lift(send_input('<c-j>'))
    yield NS.lift(send_input('<c-k>'))
    yield NS.lift(send_input('<c-j>'))
    content = yield NS.lift(current_buffer_matches(have_length(2)))
    line, col = yield NS.lift(current_cursor())
    cursor = yield NS.lift(current_cursor_is(1, 0))
    return content & cursor


class MenuSpec(SpecBase):
    '''
    run a menu $menu
    '''

    def menu(self) -> Expectation:
        return external_state_test(test_config, menu_spec)


__all__ = ('MenuSpec',)
