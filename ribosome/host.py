import sys
import inspect
import functools
from typing import TypeVar, Type, Callable, Tuple

from neovim.msgpack_rpc import MsgpackStream, AsyncSession, Session
from neovim.plugin import Host
from neovim.api import Nvim
from neovim.msgpack_rpc.event_loop.base import BaseEventLoop
from neovim.msgpack_rpc.event_loop.asyncio import AsyncioEventLoop
from neovim.msgpack_rpc.event_loop.uv import UvEventLoop

from amino import Either, _, L, do, Path, Maybe, Lists, Right, Try, Logger

from ribosome.nvim import NvimFacade
from ribosome.logging import ribo_log, Logging
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


def host(Loop: Loop) -> PluginHost:
    sess = session(Loop)
    nvim = Nvim.from_session(sess)
    return PluginHost(nvim)


def start_host(data: Tuple[str, Type[NP]], uv_loop: bool) -> None:
    Loop = UvEventLoop if uv_loop else AsyncioEventLoop
    host(Loop).start(data)


@do
def cls_from_file(file: str) -> Either[str, Tuple[str, Type[NP]]]:
    mod = yield Either.import_file(Path(file))
    all = yield Maybe.getattr(mod, '__all__').to_either(f'file `{file}` does not define `__all__`')
    name = yield Lists.wrap(all).head.to_either(f'`{mod}.__all__` is empty')
    tpe = yield Maybe.getattr(mod, name).to_either(f'{mod}.{name} does not exist')
    yield Right((file, tpe))


@do
def cls_from_path(path: str) -> Either[str, Tuple[str, Type[NP]]]:
    tpe = yield Either.import_path(path)
    file = yield Try(inspect.getfile, tpe)
    yield Right((file, tpe))


def log() -> Logger:
    NvimFacade.stdio_with_logging('ribosome_start_host')
    return ribo_log


def start(desc: str, target: str, cls: Callable[[str], Either[str, Tuple[str, Type[NP]]]]) -> None:
    def error(msg: str) -> None:
        log().error(f'invalid rplugin {desc} `{target}`: {msg}')
    try:
        cls(target).map(L(start_host)(_, True)).leffect(error)
    except Exception as e:
        log().caught_exception_error(f'starting host with {desc} `{target}`', e)


def start_file(file: str) -> None:
    start('file', file, cls_from_file)


def start_cls(cls: str) -> None:
    start('class', cls, cls_from_path)


def cli() -> None:
    start_file(sys.argv[1])


__all__ = ('start_host', 'cli', 'start_file', 'start_cls')
