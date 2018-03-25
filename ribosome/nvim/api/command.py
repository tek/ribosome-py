from typing import Any, TypeVar

from amino import L

from ribosome.nvim.io import NvimIO
from ribosome.nvim.api.util import run_once_defined, cons_split_lines

A = TypeVar('A')


def nvim_command(cmd: str, *args: Any, verbose: bool=False) -> NvimIO[None]:
    arg_string = ' '.join(map(str, args))
    silent = 'silent! ' if verbose else ''
    return NvimIO.write('nvim_command', f'{silent}{cmd} {arg_string}')


def nvim_command_output(cmd: str, *args: Any) -> NvimIO[None]:
    arg_string = ' '.join(map(str, args))
    return NvimIO.read_cons('nvim_command_output', cons_split_lines, f'{cmd} {arg_string}')


def command_once_defined(name: str, *args: str, timeout: int=10) -> NvimIO[A]:
    return run_once_defined(
        L(nvim_command)(name, *args),
        f'cmd `{name}` did not appear',
        timeout=timeout
    )


def doautocmd(name: str, pattern: str='') -> NvimIO[None]:
    return nvim_command(f'doautocmd <nomodeline> {name} {pattern}')


__all__ = ('nvim_command', 'nvim_command_output', 'command_once_defined', 'doautocmd')
