from typing import TypeVar, Callable, Generic, Tuple

from amino import do, Do, List, Just
from amino.case import Case
from amino.logging import module_log
from amino.lenses.lens import lens

from ribosome.util.menu.data import (Menu, MenuAction, MenuQuit, MenuPrompt, MenuUpdateLines, MenuUnit, MenuState,
                                     MenuUpdateCursor, visible_lines, MenuStackAction, MenuStackQuit, MenuStackPush,
                                     MenuStackPop, Menus, MenuPush, MenuPop, MenuQuitWith, MenuConfig, MenuContent)
from ribosome.nvim.io.compute import NvimIO
from ribosome.util.menu.prompt.run import prompt
from ribosome.nvim.scratch import (create_scratch_buffer, CreateScratchBufferOptions, ScratchBuffer,
                                   set_scratch_buffer_content, focus_scratch_window)
from ribosome.util.menu.prompt.data import (InputChar, InputState, PromptAction, PromptUnit, PromptStateTrans,
                                            PromptConsumerUpdate, PromptQuit)
from ribosome.nvim.io.state import NS
from ribosome.nvim.api.ui import set_cursor, close_buffer, window_set_height, wincmd
from ribosome.compute.prog import Prog
from ribosome.compute.ribosome_api import Ribo
from ribosome.nvim.io.api import N
from ribosome.nvim.api.command import nvim_command

log = module_log()
S = TypeVar('S')
ML = TypeVar('ML')
U = TypeVar('U')


@do(NvimIO[None])
def cleanup_menu(scratch: ScratchBuffer) -> Do:
    yield N.recover_failure(close_buffer(scratch.buffer), lambda a: N.unit)


@do(NS[InputState[MenuState[S, ML, U], U], PromptAction])
def menu_reentry(
        handle_input: Callable[[PromptConsumerUpdate[U]], NS[InputState[MenuState[S, ML, U], U], MenuAction]],
        scratch: ScratchBuffer,
        config: MenuConfig[S, ML, U],
) -> Do:
    state = yield NS.get()
    return NS.lift(prompt(update_menu(handle_input, scratch, config), state, config.insert))


def display_lines(config: MenuConfig[S, ML, U], content: MenuContent[ML]) -> List[str]:
    lines = visible_lines(content).map(lambda a: a.text)
    return (
        lines.reversed
        if config.bottom else
        lines
    )


@do(NS[InputState[MenuState[S, ML, U], U], None])
def menu_update_cursor(bottom: bool, scratch: ScratchBuffer) -> Do:
    cursor = yield NS.inspect(lambda a: a.data.cursor)
    total = yield NS.inspect(lambda a: len(a.data.content.lines))
    line = total - cursor if bottom else cursor + 1
    yield NS.lift(set_cursor(scratch.ui.window, (line, 0)))
    yield NS.lift(nvim_command('redraw'))


class execute_menu_action(Case[MenuAction, NS[InputState[MenuState[S, ML, U], U], PromptAction]], alg=MenuAction):

    def __init__(
            self,
            scratch: ScratchBuffer,
            handle_input: Callable[[PromptConsumerUpdate[U]], NS[InputState[MenuState[S, ML, U], U], MenuAction]],
            config: MenuConfig[S, ML, U],
    ) -> None:
        self.scratch = scratch
        self.handle_input = handle_input
        self.config = config

    def quit(self, action: MenuQuit) -> NS[InputState[MenuState[S, ML, U], U], PromptAction]:
        return NS.pure(PromptQuit())

    @do(NS[InputState[MenuState[S, ML, U], U], PromptAction])
    def quit_with(self, action: MenuQuitWith) -> Do:
        yield NS.modify(lens.data.result.set(Just(action.next)))
        return PromptQuit()

    def prompt_state_trans(self, action: MenuPrompt) -> NS[InputState[MenuState[S, ML, U], U], PromptAction]:
        return NS.pure(PromptStateTrans(action.state))

    @do(NS[InputState[MenuState[S, ML, U], U], PromptAction])
    def update_lines(self, action: MenuUpdateLines) -> Do:
        lines = display_lines(self.config, action.content)
        height = max(1, min(len(lines), self.config.max_size.get_or_strict(1000)))
        yield NS.modify(lens.data.content.set(action.content))
        yield NS.lift(window_set_height(self.scratch.ui.window, height))
        yield NS.lift(set_scratch_buffer_content(self.scratch, lines))
        yield menu_update_cursor(self.config.bottom, self.scratch)
        return PromptUnit()

    @do(NS[InputState[MenuState[S, ML, U], U], PromptAction])
    def update_cursor(self, a: MenuUpdateCursor) -> Do:
        yield menu_update_cursor(self.config.bottom, self.scratch)
        return PromptUnit()

    @do(NS[InputState[MenuState[S, ML, U], U], PromptAction])
    def push(self, action: MenuPush) -> Do:
        current = yield menu_reentry(self.handle_input, self.scratch, self.config)
        yield NS.modify(lens.data.next.set(MenuStackPush(current, action.thunk(self.scratch))))
        return PromptQuit()

    @do(NS[InputState[MenuState[S, ML, U], U], PromptAction])
    def pop(self, action: MenuPop) -> Do:
        yield NS.modify(lens.data.next.set(MenuStackPop()))
        return PromptQuit()

    def unit(self, a: MenuUnit) -> NS[InputState[MenuState[S, ML, U], U], PromptAction]:
        return NS.pure(PromptUnit())


def update_menu(
        handle_input: Callable[[PromptConsumerUpdate[U]], NS[InputState[MenuState[S, ML, U], U], MenuAction]],
        scratch: ScratchBuffer,
        config: MenuConfig[S, ML, U],
) -> Callable[[InputChar], NS[InputState[MenuState[S, ML, U], U], PromptAction]]:
    @do(NS[InputState[MenuState[S, ML, U], U], PromptAction])
    def update_menu(update: PromptConsumerUpdate[U]) -> Do:
        action = yield handle_input(update)
        yield execute_menu_action(scratch, handle_input, config)(action)
    return update_menu


class menu_recurse(Generic[S, ML], Case[MenuStackAction, NS[Menus, Prog[None]]], alg=MenuStackAction):

    def __init__(self, result: MenuState[S, ML, U]) -> None:
        self.result = result

    def quit(self, action: MenuStackQuit) -> NS[Menus, Prog[None]]:
        return NS.pure(self.result.result)

    @do(NS[Menus, Prog[None]])
    def push(self, action: MenuStackPush) -> Do:
        yield NS.modify(lambda a: a.mod.stack(lambda b: b.cons(action.current)))
        yield action.thunk

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


def menu_prompt(menu: Menu[S, ML, U], scratch: ScratchBuffer) -> NvimIO[MenuState[S, ML, U]]:
    state = MenuState.cons(menu.initial_state, menu.config, MenuContent.cons(menu.lines))
    return prompt(update_menu(menu.handle_input, scratch, menu.config), state, menu.config.insert)


@do(NS[Menus, Prog[None]])
def menu_loop(menu: Menu[S, ML, U], scratch: ScratchBuffer) -> Do:
    result = yield NS.lift(menu_prompt(menu, scratch))
    yield menu_recurse(result)(result.next)


@do(NvimIO[Prog[None]])
def run_menu(menu: Menu[S, ML, U]) -> Do:
    scratch = yield create_scratch_buffer(CreateScratchBufferOptions.cons(wrap=False, name=menu.config.name))
    yield wincmd(scratch.ui.window, 'J')
    yield focus_scratch_window(scratch)
    state, next = yield N.ensure(menu_loop(menu, scratch).run(Menus.cons()), lambda a: cleanup_menu(scratch))
    return next.get_or_strict(Prog.unit).replace(state)


@do(Prog[S])
def run_menu_prog(menu: Menu[S, ML, U]) -> Do:
    next = yield Ribo.lift_nvimio(run_menu(menu))
    yield next


def menu_push(menu: Menu[S, ML, U]) -> MenuPush:
    return MenuPush(lambda scratch: menu_loop(menu, scratch))


__all__ = ('run_menu', 'run_menu_prog',)
