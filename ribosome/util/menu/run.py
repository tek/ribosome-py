from typing import TypeVar, Callable

from amino import do, Do
from amino.case import Case

from ribosome.util.menu.data import (Menu, MenuAction, MenuQuit, MenuPrompt, MenuRedraw, MenuQuitWith, MenuUnit,
                                     MenuState)
from ribosome.nvim.io.compute import NvimIO
from ribosome.util.menu.prompt.run import prompt
from ribosome.nvim.scratch import (create_scratch_buffer, CreateScratchBufferOptions, ScratchBuffer,
                                   set_scratch_buffer_content)
from ribosome.util.menu.prompt.data import (InputChar, InputState, PromptAction, PromptQuit, PromptUnit, PromptQuitWith,
                                            PromptStateTrans)
from ribosome.nvim.io.state import NS

A = TypeVar('A')
B = TypeVar('B')
C = TypeVar('C')


class execute_menu_action(Case[MenuAction, NS[InputState[A, B], PromptAction]], alg=MenuAction):

    def __init__(self, scratch: ScratchBuffer) -> None:
        self.scratch = scratch

    def quit(self, a: MenuQuit) -> NS[InputState[A, B], PromptAction]:
        return NS.pure(PromptQuit())

    def quit_with(self, a: MenuQuitWith) -> NS[InputState[A, B], PromptAction]:
        return NS.pure(PromptQuitWith(a.prog))

    def prompt(self, a: MenuPrompt) -> NS[InputState[A, B], PromptAction]:
        return NS.pure(PromptStateTrans(a.state))

    @do(NS[InputState[A, B], PromptAction])
    def redraw(self, a: MenuRedraw) -> Do:
        yield NS.lift(set_scratch_buffer_content(self.scratch, a.content.filtered.map(lambda a: a.text)))
        return PromptUnit()

    def unit(self, a: MenuUnit) -> NS[InputState[A, B], PromptAction]:
        return NS.pure(PromptUnit())


def update_menu(
        menu: Menu,
        scratch: ScratchBuffer,
) -> Callable[[InputChar], NS[InputState[MenuState[A, B], C], PromptAction]]:
    @do(NS[InputState[MenuState[A, B], C], PromptAction])
    def update_menu(char: InputChar) -> Do:
        action = yield menu.config.handle_input(char)
        yield execute_menu_action(scratch)(action)
    return update_menu


@do(NvimIO[None])
def run_menu(menu: Menu) -> Do:
    scratch = yield create_scratch_buffer(CreateScratchBufferOptions.cons(wrap=False, name=menu.config.name))
    yield prompt(update_menu(menu, scratch), menu.state)


__all__ = ('run_menu',)
