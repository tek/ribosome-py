import sys
import functools
from typing import TypeVar, Tuple, Type

import neovim
from neovim.msgpack_rpc import MsgpackStream, AsyncSession, Session
from neovim.plugin import Host
from neovim.api import Nvim
from neovim.msgpack_rpc.event_loop.base import BaseEventLoop
from neovim.msgpack_rpc.event_loop.asyncio import AsyncioEventLoop
from neovim.msgpack_rpc.event_loop.uv import UvEventLoop

from amino import Either, _, L

from ribosome.nvim import NvimFacade
from ribosome.logging import nvim_logging, ribo_log, Logging
from ribosome.rpc import rpc_handler_functions, RpcHandlerFunction
from ribosome import NvimPlugin

Loop = TypeVar('Loop', bound=BaseEventLoop)
NP = TypeVar('NP', bound=NvimPlugin)


class PluginHost(Host, Logging):

    def _load(self, data: Tuple[str, Type[NP]]) -> None:
        file, tpe = data
        instance = tpe(self._configure_nvim_for(tpe))
        handlers = rpc_handler_functions(instance)
        handlers % L(self.register)(file, _)
        self._specs[file] = handlers / _.spec.encode

    def register(self, file: str, handler: RpcHandlerFunction) -> None:
        spec = handler.spec
        method = spec.rpc_method(file)
        func = functools.partial(self._wrap_function, handler.func, spec.sync, True, None, method)
        self._copy_attributes(handler.func, func)
        target = self._request_handlers if spec.sync else self._notification_handlers
        target[method] = func


def session(Loop: Loop, *args: str, transport_type='stdio', **kwargs: str) -> Session:
    return Session(AsyncSession(MsgpackStream(Loop(transport_type, *args, **kwargs))))


def common(Loop: Loop, plug: str, tpe: Type[NP]) -> None:
    sess = session(Loop)
    nvim = Nvim.from_session(sess)
    host = PluginHost(nvim)
    host.start((plug, tpe))


def start_asyncio_host(plug: str, tpe: Type[NP]) -> None:
    common(AsyncioEventLoop, plug, tpe)


def start_uv_host(plug: str, tpe: Type[NP]) -> None:
    common(UvEventLoop, plug, tpe)


def start_host(plug: str, cls: str, uv_loop: bool) -> None:
    def go(tpe: Type[NP]) -> None:
        (start_uv_host if uv_loop else start_asyncio_host)(plug, tpe)
    return Either.import_path(cls) % go


def cli() -> None:
    native = neovim.attach('stdio')
    vim = NvimFacade(native, 'ribosome_start_host')
    nvim_logging(vim)
    file, cls = sys.argv[1:3]
    def error(msg: str) -> None:
        ribo_log.error(f'invalid rplugin class: {cls}')
    try:
        start_host(file, cls, False).leffect(error)
    except Exception as e:
        ribo_log.caught_exception_error(f'starting host with args `{sys.argv}`', e)


__all__ = ('start_host', 'cli')
