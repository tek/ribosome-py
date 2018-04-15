from typing import Callable, TypeVar, Any

from amino import do, Do, Either, Right, Left

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.function import nvim_call_cons, nvim_call_function
from ribosome.nvim.api.util import nvimio_repeat_timeout, cons_checked_e
from ribosome.nvim.api.command import nvim_command

A = TypeVar('A')


def check_exists_bool(a: Any) -> Either[str, bool]:
    return Right(a != 0) if a in [0, 1, 2] else Left(f'nvim result is not an exists-boolean: {a}')


cons_decode_exists_bool = cons_checked_e(int, check_exists_bool)


def nvim_exists(target: str) -> NvimIO[bool]:
    return nvim_call_cons(cons_decode_exists_bool, 'exists', target)


def wait_until_valid(name: str, check: Callable[[str], NvimIO[bool]], timeout: int=30) -> NvimIO[None]:
    return nvimio_repeat_timeout(
        lambda: check(name),
        lambda a: a,
        f'{name} did not appear after {timeout} seconds',
        timeout
    )


def function_exists(name: str) -> NvimIO[bool]:
    return nvim_exists(f'*{name}')


def command_exists(name: str) -> NvimIO[bool]:
    return nvim_exists(f':{name}')


def wait_for_function(name: str, timeout: int=30) -> NvimIO[None]:
    return wait_until_valid(name, function_exists, timeout)


def wait_for_command(name: str, timeout: int=30) -> NvimIO[None]:
    return wait_until_valid(name, command_exists, timeout)


@do(NvimIO[A])
def command_once_defined(name: str, *args: str, timeout: int=30, verbose: bool=False) -> Do:
    yield wait_for_command(name, timeout)
    yield nvim_command(name, *args, verbose=verbose)


@do(NvimIO[A])
def call_once_defined(name: str, *args: str, timeout: int=10) -> Do:
    yield wait_for_function(name, timeout)
    yield nvim_call_function(name, *args)


__all__ = ('nvim_exists', 'wait_until_valid', 'function_exists', 'command_exists', 'wait_for_function',
           'wait_for_command', 'command_once_defined', 'call_once_defined')
