from typing import Callable, TypeVar

from ribosome.config.settings import Settings

from amino import Either
from ribosome.config.setting import Setting
from ribosome.nvim.io.state import NS
from ribosome.config.resources import Resources
from ribosome.data.plugin_state import PluginState
from ribosome.nvim.io.compute import NvimIO

A = TypeVar('A')
S = TypeVar('S', bound=Settings)
D = TypeVar('D')
CC = TypeVar('CC')


def setting(attr: Callable[[S], Setting[A]]) -> NS[Resources[S, D, CC], A]:
    def get(res: Resources[S, D, CC]) -> NvimIO[A]:
        return attr(res.settings).value_or_default
    return NS.inspect_f(get)


def setting_ps(attr: Callable[[S], Setting[A]]) -> NS[PluginState[S, D, CC], A]:
    def get(ps: PluginState[S, D, CC]) -> NvimIO[A]:
        return attr(ps.basic.settings).value_or_default
    return NS.inspect_f(get)


def setting_ps_e(attr: Callable[[S], Setting[A]]) -> NS[PluginState[S, D, CC], Either[str, A]]:
    def get(ps: PluginState[S, D, CC]) -> NvimIO[Either[str, A]]:
        return attr(ps.basic.settings).value
    return NS.inspect_f(get)


__all__ = ('setting', 'setting_ps', 'setting_ps_e')
