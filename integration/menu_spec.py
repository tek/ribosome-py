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
from ribosome.util.menu.run import run_menu_prog
from ribosome.util.menu.data import MenuContent, Menu, MenuLine, MenuQuitWith
from ribosome.util.menu.auto.data import AutoS, AutoState
from ribosome.compute.prog import Prog
from ribosome.data.plugin_state import PS

log = module_log()


class SM(Dat['SM']):

    @staticmethod
    def cons(
    ) -> 'SM':
        return SM(
        )

    def __init__(self) -> None:
        pass


@prog
@do(NS[PS, None])
def process_selected(items: List[MenuLine[None]]) -> Do:
    buf = yield NS.lift(current_buffer())
    yield NS.lift(set_buffer_content(buf, items.map(lambda a: a.text)))


@do(AutoS[None, None, SM])
def item_selected() -> Do:
    items = yield selected_menu_lines()
    return MenuQuitWith(process_selected(items))


lines = List('first', 'second', 'third').map(lambda a: MenuLine.cons(a, None))
menu: Menu[AutoState[None, None, SM], None, None] = auto_menu(
    SM(), MenuContent.cons(lines), 'submenu', Map({'<cr>': item_selected})
)


@prog.do(None)
def run() -> Do:
    yield run_menu_prog(menu)
    yield Prog.unit


config: Config[SM, None] = Config.cons(
    'submenu',
    rpc=List(rpc.write(run)),
    state_ctor=SM.cons,
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
    yield send_input('<esc>')
    yield send_input('<space>')
    yield send_input('*')
    yield N.sleep(.5)
    yield send_input('<cr>')
    yield screenshot('menu', 'sub', 'final')


class SubMenuSpec(SpecBase):
    '''
    launch a submenu $submenu
    '''

    def submenu(self) -> Expectation:
        return tmux_plugin_test(test_config, submenu_spec)


__all__ = ('SubMenuSpec',)
