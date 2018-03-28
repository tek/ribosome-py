from typing import Callable, TypeVar, Any

from amino import Either, List, do, Do, Right

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.util import cons_decode_str, cons_decode_str_list, cons_decode_str_list_option
from ribosome.nvim.api.data import Buffer
from ribosome.nvim.io.api import N

A = TypeVar('A')
B = TypeVar('B')


def option(name: str, cons: Callable[[A], Either[str, B]]) -> NvimIO[B]:
    return N.read_cons('nvim_get_option', cons, name)


def option_str(name: str) -> NvimIO[str]:
    return option(name, cons_decode_str)


def option_str_list(name: str) -> NvimIO[List[str]]:
    return option(name, cons_decode_str_list)


def option_set(name: str, value: Any) -> NvimIO[None]:
    return N.write('nvim_set_option', name, value)


@do(NvimIO[None])
def option_modify(name: str, cons: Callable[[A], Either[str, B]], modify: Callable[[B], Either[str, B]]) -> Do:
    value = yield option(name, cons)
    new = yield N.from_either(modify(value))
    yield option_set(name, new)


def option_cat(name: str, add: List[str]) -> NvimIO[None]:
    return option_modify(name, cons_decode_str_list_option, lambda a: Right((a + add.map(str)).mk_string(',')))


def option_buffer_set(buffer: Buffer, name: str, value: Any) -> NvimIO[None]:
    return N.write('nvim_buf_set_option', buffer.data, name, value)


__all__ = ('option', 'option_str', 'option_str_list', 'option_set', 'option_modify', 'option_cat', 'option_buffer_set')
