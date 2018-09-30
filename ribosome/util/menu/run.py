from typing import TypeVar, Callable

from amino import do, Do
from amino.case import Case
from amino.logging import module_log

from ribosome.util.menu.data import (Menu, MenuAction, MenuQuit, MenuPrompt, MenuUpdateLines, MenuQuitWith, MenuUnit,
                                     MenuState, MenuUpdateCursor, visible_lines)
from ribosome.nvim.io.compute import NvimIO
from ribosome.util.menu.prompt.run import prompt
from ribosome.nvim.scratch import (create_scratch_buffer, CreateScratchBufferOptions, ScratchBuffer,
                                   set_scratch_buffer_content)
from ribosome.util.menu.prompt.data import (InputChar, InputState, PromptAction, PromptQuit, PromptUnit, PromptQuitWith,
                                            PromptStateTrans, PromptUpdate)
from ribosome.nvim.io.state import NS
from ribosome.nvim.api.ui import set_cursor, close_buffer
from ribosome.compute.prog import Prog
from ribosome.compute.ribosome_api import Ribo
from ribosome.compute.api import prog
from ribosome.nvim.io.api import N

log = module_log()
A = TypeVar('A')
B = TypeVar('B')
C = TypeVar('C')


@prog
@do(NS[None, None])
def cleanup_menu(scratch: ScratchBuffer) -> Do:
    yield NS.lift(N.recover_failure(close_buffer(scratch.buffer), lambda a: N.unit))


@prog.do(None)
def quit_menu(scratch: ScratchBuffer, next: Prog[None]) -> Do:
    yield cleanup_menu(scratch)
    yield next


class execute_menu_action(Case[MenuAction, NS[InputState[MenuState[A, B], C], PromptAction]], alg=MenuAction):

    def __init__(self, scratch: ScratchBuffer) -> None:
        self.scratch = scratch

    def quit(self, action: MenuQuit) -> NS[InputState[MenuState[A, B], C], PromptAction]:
        return NS.pure(PromptQuitWith(quit_menu(self.scratch, Prog.unit)))

    def quit_with(self, action: MenuQuitWith) -> NS[InputState[MenuState[A, B], C], PromptAction]:
        return NS.pure(PromptQuitWith(quit_menu(self.scratch, action.prog)))

    def prompt(self, action: MenuPrompt) -> NS[InputState[MenuState[A, B], C], PromptAction]:
        return NS.pure(PromptStateTrans(action.state))

    @do(NS[InputState[MenuState[A, B], C], PromptAction])
    def update_lines(self, action: MenuUpdateLines) -> Do:
        yield NS.lift(set_scratch_buffer_content(self.scratch, visible_lines(action.content).map(lambda a: a.text)))
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
