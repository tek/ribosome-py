from typing import Any, TypeVar

from ribosome.nvim.io.compute import NvimIO

from amino import List, do, Do
from ribosome.nvim.api.util import cons_split_lines
from ribosome.nvim.io.api import N

A = TypeVar('A')


def nvim_command(cmd: str, *args: Any, verbose: bool=False, sync: bool=False) -> NvimIO[None]:
    verbose = True
    arg_string = ' '.join(map(str, args))
    arg_suffix = '' if len(args) == 0 else f' {arg_string}'
    silent = '' if verbose else 'silent! '
    return N.write('nvim_command', f'{silent}{cmd}{arg_suffix}', sync=sync)


def nvim_sync_command(cmd: str, *args: Any, verbose: bool=False) -> NvimIO[None]:
    return nvim_command(cmd, *args, verbose=verbose, sync=True)


def nvim_command_output(cmd: str, *args: Any) -> NvimIO[None]:
    arg_string = ' '.join(map(str, args))
    return N.read_cons('nvim_command_output', cons_split_lines, f'{cmd} {arg_string}')


def doautocmd(name: str, pattern: str='', verbose: bool=False, sync: bool=False) -> NvimIO[None]:
    return nvim_command(f'doautocmd', '<nomodeline>', name, pattern, verbose=verbose, sync=sync)


def runtime(path: str, verbose: bool=True, sync: bool=False) -> NvimIO[None]:
    return nvim_command('runtime!', f'{path}.vim', verbose=verbose, sync=sync)


def defined_commands() -> NvimIO[List[str]]:
    return nvim_command_output('command')


@do(NvimIO[str])
def defined_commands_str() -> Do:
    lines = yield defined_commands()
    return lines.join_lines


__all__ = ('nvim_command', 'nvim_command_output', 'doautocmd', 'runtime', 'nvim_sync_command', 'defined_commands',
           'defined_commands_str',)
