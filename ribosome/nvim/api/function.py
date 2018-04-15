from typing import Any, Type, TypeVar, Callable

from ribosome.nvim.io.compute import NvimIO

from amino import Either, List
from ribosome.nvim.api.command import nvim_command
from ribosome.nvim.request import nvim_request
from ribosome.nvim.io.api import N

A = TypeVar('A')


def nvim_call_function(fun: str, *args: Any) -> NvimIO[Any]:
    return nvim_request('nvim_call_function', fun, args)


def nvim_call_tpe(tpe: Type[A], fun: str, *args: Any) -> NvimIO[A]:
    return N.read_tpe('nvim_call_function', tpe, fun, args)


def nvim_call_cons(cons: Callable[[Any], Either[str, A]], fun: str, *args: Any) -> NvimIO[A]:
    return N.read_cons('nvim_call_function', cons, fun, args)


def define_function(name: str, params: List[str], body: str) -> NvimIO[None]:
    return nvim_command(f'function!', f'{name}({params.join_comma})\n{body}\nendfunction')



__all__ = ('nvim_call_function', 'nvim_call_tpe', 'nvim_call_cons', 'define_function')
