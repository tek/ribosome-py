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
from ribosome.nvim.api.ui import send_input, current_buffer, set_buffer_content
from ribosome.nvim.io.api import N
from ribosome.util.menu.auto.run import auto_menu, selected_menu_lines
from ribosome.util.menu.run import run_menu_prog, update_menu
from ribosome.util.menu.data import MenuContent, Menu, MenuLine, MenuQuitWith, MenuPush
from ribosome.util.menu.auto.data import AutoS, AutoState
from ribosome.compute.prog import Prog
from ribosome.data.plugin_state import PS
from ribosome.util.menu.prompt.run import prompt

log = module_log()


@prog
@do(NS[PS, None])
def process_selected(items: List[MenuLine[None]]) -> Do:
    buf = yield NS.lift(current_buffer())
    yield NS.lift(set_buffer_content(buf, items.map(lambda a: f'selected {a.text}')))


@do(AutoS)
def sub_item_selected() -> Do:
    items = yield selected_menu_lines()
    return MenuQuitWith(process_selected(items))


def sub_menu(primary: List[MenuLine[None]]) -> Menu[AutoState[None, None, None], None, None]:
    lines = primary.map(lambda a: MenuLine.cons(f'sub {a.text}', None))
    return auto_menu(None, MenuContent.cons(lines), 'submenu', Map({'<cr>': sub_item_selected}))


@do(AutoS)
def start_sub() -> Do:
    items = yield selected_menu_lines()
    menu = sub_menu(items)
    return MenuPush(lambda scratch: NS.lift(prompt(update_menu(menu.config, scratch), menu.state)))


lines = List('first', 'second', 'third').map(lambda a: MenuLine.cons(a, None))
main_menu: Menu[AutoState, None, None] = auto_menu(
    None,
    MenuContent.cons(lines),
    'mainmenu',
    Map({'<tab>': start_sub}),
)


@prog.do(None)
def run() -> Do:
    yield run_menu_prog(main_menu)
    yield Prog.unit


config: Config = Config.cons(
    'submenu',
    rpc=List(rpc.write(run)),
)
vars = Map(
    submenu_tmux_socket=tmux_spec_socket,
)
test_config = TestConfig.cons(config, vars=vars)


@do(NvimIO[Expectation])
def submenu_spec() -> Do:
    yield send_input(':call SubmenuRun()<cr>')
    yield N.sleep(.1)
    yield send_input('ir')
    shot1 = yield screenshot('menu', 'sub', 'filtered')
    yield send_input('<esc>')
    yield send_input('<space>')
    yield send_input('*')
    yield send_input('<tab>')
    shot2 = yield screenshot('menu', 'sub', 'submenu')
    yield send_input('<cr>')
    shot3 = yield screenshot('menu', 'sub', 'final')
    return shot1 & shot2 & shot3


class SubMenuSpec(SpecBase):
    '''
    launch a submenu $submenu
    '''

    def submenu(self) -> Expectation:
        return tmux_plugin_test(test_config, submenu_spec)


__all__ = ('SubMenuSpec',)
