from typing import Callable, TypeVar

from ribosome.config.settings import Settings
from ribosome.config.setting import Setting
from ribosome.nvim.io.state import NS
from ribosome.config.resources import Resources

A = TypeVar('A')
S = TypeVar('S', bound=Settings)
D = TypeVar('D')
CC = TypeVar('CC')


def setting(attr: Callable[[S], Setting[A]]) -> NS[Resources[D, S, CC], A]:
    return NS.inspect_f(lambda a: attr(a.settings).value_or_default)


__all__ = ('setting',)
