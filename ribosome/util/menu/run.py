from typing import TypeVar, Callable, Generic, Tuple

from amino import do, Do, List, Just
from amino.case import Case
from amino.logging import module_log
from amino.lenses.lens import lens

from ribosome.util.menu.data import (Menu, MenuAction, MenuQuit, MenuPrompt, MenuUpdateLines, MenuUnit, MenuState,
                                     MenuUpdateCursor, visible_lines, MenuStackAction, MenuStackQuit, MenuStackPush,
                                     MenuStackPop, Menus, MenuPush, MenuPop, MenuQuitWith, MenuConfig)
from ribosome.nvim.io.compute import NvimIO
from ribosome.util.menu.prompt.run import prompt
from ribosome.nvim.scratch import (create_scratch_buffer, CreateScratchBufferOptions, ScratchBuffer,
                                   set_scratch_buffer_content)
from ribosome.util.menu.prompt.data import (InputChar, InputState, PromptAction, PromptUnit, PromptStateTrans,
                                            PromptUpdate, PromptQuit)
from ribosome.nvim.io.state import NS
from ribosome.nvim.api.ui import set_cursor, close_buffer
from ribosome.compute.prog import Prog
from ribosome.compute.ribosome_api import Ribo
from ribosome.nvim.io.api import N

log = module_log()
S = TypeVar('S')
ML = TypeVar('ML')
U = TypeVar('U')


@do(NvimIO[None])
def cleanup_menu(scratch: ScratchBuffer) -> Do:
    yield N.recover_failure(close_buffer(scratch.buffer), lambda a: N.unit)


@do(NS[InputState[MenuState[S, ML], U], PromptAction])
def menu_reentry(config: MenuConfig[S, ML, U], scratch: ScratchBuffer) -> Do:
    state = yield NS.get()
    return NS.lift(prompt(update_menu(config, scratch), state))


class execute_menu_action(Case[MenuAction, NS[InputState[MenuState[S, ML], U], PromptAction]], alg=MenuAction):

    def __init__(self, scratch: ScratchBuffer, config: MenuConfig[S, ML, U]) -> None:
        self.scratch = scratch
        self.config = config

    def quit(self, action: MenuQuit) -> NS[InputState[MenuState[S, ML], U], PromptAction]:
        return NS.pure(PromptQuit())

    @do(NS[InputState[MenuState[S, ML], U], PromptAction])
    def quit_with(self, action: MenuQuitWith) -> Do:
        yield NS.modify(lens.data.result.set(Just(action.next)))
        return PromptQuit()

    def prompt_state_trans(self, action: MenuPrompt) -> NS[InputState[MenuState[S, ML], U], PromptAction]:
        return NS.pure(PromptStateTrans(action.state))

    @do(NS[InputState[MenuState[S, ML], U], PromptAction])
    def update_lines(self, action: MenuUpdateLines) -> Do:
        yield NS.lift(set_scratch_buffer_content(self.scratch, visible_lines(action.content).map(lambda a: a.text)))
        return PromptUnit()

    @do(NS[InputState[MenuState[S, ML], U], PromptAction])
    def update_cursor(self, a: MenuUpdateCursor) -> Do:
        line = yield NS.inspect(lambda a: a.data.cursor)
        yield NS.lift(set_cursor(self.scratch.ui.window, (line + 1, 0)))
        return PromptUnit()

    @do(NS[InputState[MenuState[S, ML], U], PromptAction])
    def push(self, action: MenuPush) -> Do:
        current = yield menu_reentry(self.config, self.scratch)
        yield NS.modify(lens.data.next.set(MenuStackPush(current, action.thunk(self.scratch))))
        return PromptQuit()

    @do(NS[InputState[MenuState[S, ML], U], PromptAction])
    def pop(self, action: MenuPop) -> Do:
        yield NS.modify(lens.data.next.set(MenuStackPop()))
        return PromptQuit()

    def unit(self, a: MenuUnit) -> NS[InputState[MenuState[S, ML], U], PromptAction]:
        return NS.pure(PromptUnit())


def update_menu(
        config: MenuConfig[S, ML, U],
        scratch: ScratchBuffer,
) -> Callable[[InputChar], NS[InputState[MenuState[S, ML], U], PromptAction]]:
    @do(NS[InputState[MenuState[S, ML], U], PromptAction])
    def update_menu(update: PromptUpdate[U]) -> Do:
        action = yield config.handle_input(update)
        yield execute_menu_action(scratch, config)(action)
    return update_menu


class menu_recurse(Generic[S, ML], Case[MenuStackAction, NS[Menus, Prog[None]]], alg=MenuStackAction):

    def __init__(self, result: MenuState[S, ML]) -> None:
        self.result = result

    def quit(self, action: MenuStackQuit) -> NS[Menus, Prog[None]]:
        return NS.pure(self.result.result)

    @do(NS[Menus, Prog[None]])
    def push(self, action: MenuStackPush) -> Do:
        yield NS.modify(lambda a: a.mod.stack(lambda b: b.cons(action.current)))
        result = yield action.thunk
        yield menu_recurse(result)(result.next)

    @do(NS[Menus, Prog[None]])
    def pop(self, action: MenuStackPop) -> Do:
        stack = yield NS.inspect(lambda a: a.stack)
        def push(
                menus: Menus,
                h: NS[Menus, Prog[None]],
                t: List[Menus, Prog[None]],
        ) -> NvimIO[Tuple[Menus, NS[Menus, Prog[None]]]]:
            return N.pure((menus.set.stack(t), h))
        next = yield stack.detach_head.map2(
            lambda h, t: NS.apply(lambda a: push(a, h, t))
        ).get_or(NS.pure, NS.pure(self.result.result))
        yield next


@do(NS[Menus, Prog[None]])
def menu_loop(menu: Menu[S, ML, U], scratch: ScratchBuffer) -> Do:
    result = yield NS.lift(prompt(update_menu(menu.config, scratch), menu.state))
    yield menu_recurse(result)(result.next)


@do(NvimIO[Prog[None]])
def run_menu(menu: Menu[S, ML, U]) -> Do:
    scratch = yield create_scratch_buffer(CreateScratchBufferOptions.cons(wrap=False, name=menu.config.name))
    state, next = yield N.ensure(menu_loop(menu, scratch).run(Menus.cons()), lambda a: cleanup_menu(scratch))
    return next.get_or_strict(Prog.unit).replace(state)


@do(Prog[S])
def run_menu_prog(menu: Menu[S, ML, U]) -> Do:
    next = yield Ribo.lift_nvimio(run_menu(menu))
    yield next


__all__ = ('run_menu', 'run_menu_prog',)
