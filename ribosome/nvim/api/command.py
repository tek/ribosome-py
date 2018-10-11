from typing import Any, TypeVar, Callable

from ribosome.nvim.io.compute import NvimIO, NRParams

from amino import List, do, Do, Either, Lists, Right, Left
from amino.logging import module_log
from ribosome.nvim.api.util import cons_split_lines, cons_checked_e
from ribosome.nvim.io.api import N

log = module_log()
A = TypeVar('A')


def nvim_command(cmd: str, *args: Any, params: NRParams=NRParams.cons(verbose=False, sync=False)) -> NvimIO[None]:
    arg_string = ' '.join(map(str, args))
    arg_suffix = '' if len(args) == 0 else f' {arg_string}'
    silent = '' if params.verbose else 'silent! '
    cmdline = f'{silent}{cmd}{arg_suffix}'
    log.debug1(lambda: f'nvim command `{cmdline}`')
    return N.write('nvim_command', cmdline, params=params)


def nvim_sync_command(cmd: str, *args: Any, params: NRParams=NRParams.cons(verbose=False, sync=True)) -> NvimIO[None]:
    return nvim_command(cmd, *args, params=params)


def nvim_command_output(cmd: str, *args: Any) -> NvimIO[None]:
    cmdline = ' '.join(map(str, (cmd,) + args))
    return N.read_cons_strict('nvim_command_output', cons_split_lines, cmdline)


def doautocmd(name: str, pattern: str='', params: NRParams=NRParams.cons(verbose=False, sync=False)) -> NvimIO[None]:
    return nvim_command(f'doautocmd', '<nomodeline>', name, pattern, params=params)


def runtime(path: str, params: NRParams=NRParams.cons(verbose=True, sync=False)) -> NvimIO[None]:
    return nvim_command('runtime!', f'{path}.vim', params=params)


def defined_commands() -> NvimIO[List[str]]:
    return nvim_command_output('command')


@do(NvimIO[str])
def defined_commands_str() -> Do:
    lines = yield defined_commands()
    return lines.join_lines


@do(Either[str, None])
def atomic_error(cmdlines: List[str], error_raw: Any) -> Do:
    error = yield (
        Right(error_raw)
        if isinstance(error_raw, list) else
        Left(f'invalid error structure for atomic call: {error_raw}')
    )
    index, tpe, message = yield (
        Lists.wrap(error)
        .lift_all(0, 1, 2)
        .to_either(f'too few elements in error structure for atomic call: {error}')
    )
    offender = yield cmdlines.lift(index).to_either(f'invalid index in atomic call error: {error}')
    yield Left(f'error of type `{tpe}` in atomic call `{offender}`: {message}')


def cons_atomic_result(cmdlines: List[str]) -> Callable[[list], Either[str, Any]]:
    @do(Either[str, Any])
    def cons(raw: list) -> Do:
        result = Lists.wrap(raw)
        results, error = yield result.lift_all(0, 1).to_either_f(lambda: f'too few elements in atomic result: {result}')
        yield (
            Right(results)
            if error is None
            else atomic_error(cmdlines, error)
        )
    return cons


def nvim_atomic_commands(cmdlines: List[str]) -> NvimIO[List[Any]]:
    cmds = cmdlines.map(lambda a: ['nvim_command', [a]])
    return N.read_cons_strict('nvim_call_atomic', cons_checked_e(list, cons_atomic_result(cmdlines)), cmds)


__all__ = ('nvim_command', 'nvim_command_output', 'doautocmd', 'runtime', 'nvim_sync_command', 'defined_commands',
           'defined_commands_str', 'nvim_atomic_commands',)
