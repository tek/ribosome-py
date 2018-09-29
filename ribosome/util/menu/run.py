from typing import TypeVar, Callable

from amino import do, Do
from amino.case import Case

from ribosome.util.menu.data import (Menu, MenuAction, MenuQuit, MenuPrompt, MenuUpdateLines, MenuQuitWith, MenuUnit,
                                     MenuState, MenuUpdateCursor)
from ribosome.nvim.io.compute import NvimIO
from ribosome.util.menu.prompt.run import prompt
from ribosome.nvim.scratch import (create_scratch_buffer, CreateScratchBufferOptions, ScratchBuffer,
                                   set_scratch_buffer_content)
from ribosome.util.menu.prompt.data import (InputChar, InputState, PromptAction, PromptQuit, PromptUnit, PromptQuitWith,
                                            PromptStateTrans, PromptUpdate)
from ribosome.nvim.io.state import NS
from ribosome.nvim.api.ui import set_cursor
from ribosome.compute.prog import Prog
from ribosome.compute.api import prog
from ribosome.compute.ribosome_api import Ribo

A = TypeVar('A')
B = TypeVar('B')
C = TypeVar('C')


class execute_menu_action(Case[MenuAction, NS[InputState[MenuState[A, B], C], PromptAction]], alg=MenuAction):

    def __init__(self, scratch: ScratchBuffer) -> None:
        self.scratch = scratch

    def quit(self, a: MenuQuit) -> NS[InputState[MenuState[A, B], C], PromptAction]:
        return NS.pure(PromptQuit())

    def quit_with(self, a: MenuQuitWith) -> NS[InputState[MenuState[A, B], C], PromptAction]:
        return NS.pure(PromptQuitWith(a.prog))

    def prompt(self, a: MenuPrompt) -> NS[InputState[MenuState[A, B], C], PromptAction]:
        return NS.pure(PromptStateTrans(a.state))

    @do(NS[InputState[MenuState[A, B], C], PromptAction])
    def update_lines(self, a: MenuUpdateLines) -> Do:
        yield NS.lift(set_scratch_buffer_content(self.scratch, a.content.filtered.map(lambda a: a.text)))
        return PromptUnit()

    @do(NS[InputState[MenuState[A, B], C], PromptAction])
    def update_cursor(self, a: MenuUpdateCursor) -> Do:
        line = yield NS.inspect(lambda a: a.data.cursor)
        yield NS.lift(set_cursor(self.scratch.ui.window, (line + 1, 0)))
        return PromptUnit()

    def unit(self, a: MenuUnit) -> NS[InputState[MenuState[A, B], C], PromptAction]:
        return NS.pure(PromptUnit())


def update_menu(
        menu: Menu[A, B, C],
        scratch: ScratchBuffer,
) -> Callable[[InputChar], NS[InputState[MenuState[A, B], C], PromptAction]]:
    @do(NS[InputState[MenuState[A, B], C], PromptAction])
    def update_menu(update: PromptUpdate[C]) -> Do:
        action = yield menu.config.handle_input(update)
        yield execute_menu_action(scratch)(action)
    return update_menu


@do(NvimIO[Prog[None]])
def run_menu(menu: Menu[A, B, C]) -> Do:
    scratch = yield create_scratch_buffer(CreateScratchBufferOptions.cons(wrap=False, name=menu.config.name))
    next, state = yield prompt(update_menu(menu, scratch), menu.state)
    return next.get_or_strict(Prog.unit).replace(state)


@do(Prog[A])
def run_menu_prog(menu: Menu[A, B, C]) -> Do:
    next = yield Ribo.lift_nvimio(run_menu(menu))
    yield next


__all__ = ('run_menu', 'run_menu_prog',)
