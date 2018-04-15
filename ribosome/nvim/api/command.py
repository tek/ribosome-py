from typing import Any, TypeVar

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.util import cons_split_lines
from ribosome.nvim.io.api import N

A = TypeVar('A')


def nvim_command(cmd: str, *args: Any, verbose: bool=False) -> NvimIO[None]:
    arg_string = ' '.join(map(str, args))
    arg_suffix = '' if len(args) == 0 else f' {arg_string}'
    silent = '' if verbose else 'silent! '
    return N.write('nvim_command', f'{silent}{cmd}{arg_suffix}')


def nvim_command_output(cmd: str, *args: Any) -> NvimIO[None]:
    arg_string = ' '.join(map(str, args))
    return N.read_cons('nvim_command_output', cons_split_lines, f'{cmd} {arg_string}')


def doautocmd(name: str, pattern: str='', verbose: bool=False) -> NvimIO[None]:
    return nvim_command(f'doautocmd', '<nomodeline>', name, pattern, verbose=verbose)


def runtime(path: str, verbose: bool=True) -> NvimIO[None]:
    return nvim_command('runtime!', f'{path}.vim', verbose=verbose)


__all__ = ('nvim_command', 'nvim_command_output', 'doautocmd', 'runtime')
