from kallikrein import Expectation
from kallikrein.matchers.length import have_length

from amino.test.spec import SpecBase
from amino import Map, List, do, Do, Dat, Nil, Just
from amino.logging import module_log

from ribosome.test.integration.external import external_state_test
from ribosome.config.config import Config
from ribosome.test.config import default_config_name, TestConfig
from ribosome.config.component import Component
from ribosome.rpc.api import rpc
from ribosome.compute.api import prog
from ribosome.nvim.io.state import NS
from ribosome.data.plugin_state import PluginState, PS
from ribosome.config.basic_config import NoData
from ribosome.test.prog import fork_request
from ribosome.util.menu.data import InputChar, MenuAction, MenuRedraw, MenuContent, MenuState, MenuLine
from ribosome.util.menu.run import run_menu, default_menu
from ribosome.nvim.api.ui import send_input
from ribosome.nvim.api.function import define_function
from ribosome.nvim.api.variable import variable_set
from ribosome.util.menu.prompt.data import InputState
from ribosome.test.klk.matchers.buffer import current_buffer_matches

log = module_log()


class MState(Dat['MState']):

    def __init__(self) -> None:
        pass


@do(NS[InputState[MenuState[MState, None], None], MenuAction])
def handle_input(key: InputChar) -> Do:
    yield NS.unit
    lines = List(
        MenuLine('first', None),
        MenuLine('second', None),
        MenuLine('third', None),
    )
    return MenuRedraw(MenuContent(lines, Just(1)))


menu_state = MState()
menu = default_menu(menu_state, handle_input, 'spec menu')


@prog.unit
@do(NS[PluginState[NoData, None], None])
def spec_menu() -> Do:
    yield NS.lift(run_menu(menu))


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
    yield NS.sleep(1)
    yield NS.lift(send_input('ir'))
    yield NS.lift(variable_set('looping', 0))
    yield NS.lift(current_buffer_matches(have_length(2)))


class MenuSpec(SpecBase):
    '''
    run a menu $menu
    '''

    def menu(self) -> Expectation:
        return external_state_test(test_config, menu_spec)


__all__ = ('MenuSpec',)
