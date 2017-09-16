import sys
import abc
import inspect
import functools
from typing import TypeVar, Type, Callable, Tuple, Generic, Generator, Any, Union

from neovim.msgpack_rpc import MsgpackStream, AsyncSession, Session
from neovim.plugin import Host
from neovim.api import Nvim
from neovim.msgpack_rpc.event_loop.base import BaseEventLoop
from neovim.msgpack_rpc.event_loop.asyncio import AsyncioEventLoop
from neovim.msgpack_rpc.event_loop.uv import UvEventLoop

from amino import Either, _, L, do, Path, Maybe, Lists, Right, Try, Logger
from amino.either import ImportFailure

from ribosome.nvim import NvimFacade
from ribosome.logging import ribo_log, Logging
from ribosome.rpc import rpc_handler_functions, RpcHandlerFunction, define_handlers
from ribosome import NvimPlugin, AutoPlugin
from ribosome.settings import Config

Loop = TypeVar('Loop', bound=BaseEventLoop)
NP = TypeVar('NP', bound=NvimPlugin)
D = TypeVar('D')


class PluginHostI(Generic[D], Host, Logging):

    @abc.abstractmethod
    def _load(self, data: D) -> None:
        ...


class PluginHost(PluginHostI[Tuple[str, Type[NP]]]):

    def _load(self, data: Tuple[str, Type[NP]]) -> None:
        file, tpe = data
        name = tpe.name or 'ribosome'
        vim = NvimFacade(self._configure_nvim_for(tpe), name)
        instance = tpe(vim)
        handlers = rpc_handler_functions(instance)
        specs = handlers / _.spec
        handlers % L(self.register)(file, _)
        self._specs[file] = specs / _.encode
        define_handlers(vim.channel_id, specs, name, file).attempt(vim).get_or_raise

    def register(self, file: str, handler: RpcHandlerFunction) -> None:
        spec = handler.spec
        method = spec.rpc_method(file)
        func = functools.partial(self._wrap_function, handler.func, spec.sync, True, None, method)
        self._copy_attributes(handler.func, func)
        target = self._request_handlers if spec.sync else self._notification_handlers
        target[method] = func


def session(Loop: Loop, *args: str, transport_type: str='stdio', **kwargs: str) -> Session:
    return Session(AsyncSession(MsgpackStream(Loop(transport_type, *args, **kwargs))))


PH = TypeVar('PH', bound=PluginHostI)


def host(loop: Loop, tpe: Type[PH]) -> PH:
    sess = session(loop)
    nvim = Nvim.from_session(sess)
    return tpe(nvim)


def start_host(data: D, uv_loop: bool, tpe: Type[PluginHostI[D]]) -> None:
    Loop = UvEventLoop if uv_loop else AsyncioEventLoop
    host(Loop, tpe).start(data)


@do
def cls_from_file(file: str) -> Either[str, Tuple[str, Type[NP]]]:
    mod = yield Either.import_file(Path(file))
    all = yield Maybe.getattr(mod, '__all__').to_either(f'file `{file}` does not define `__all__`')
    name = yield Lists.wrap(all).head.to_either(f'`{mod}.__all__` is empty')
    tpe = yield Maybe.getattr(mod, name).to_either(f'{mod}.{name} does not exist')
    yield Right((file, tpe))


@do
def cls_from_path(path: str) -> Generator[Either[str, Tuple[str, Type[NP]]], Any, None]:
    tpe = yield Either.import_path(path)
    file = yield Try(inspect.getfile, tpe)
    yield Right((file, tpe))


log_initialized = False


def log() -> Logger:
    global log_initialized
    if not log_initialized:
        NvimFacade.stdio_with_logging('ribosome_start_host')
        log_initialized = True
    return ribo_log


def start(desc: str, target: str, cls: Callable[[str], Either[str, Tuple[str, Type[NP]]]]) -> int:
    def error(msg: str) -> None:
        log().error(f'invalid rplugin {desc} `{target}`: {msg}')
    try:
        cls(target).map(L(start_host)(_, True, PluginHost)).leffect(error)
        return 0
    except Exception as e:
        log().caught_exception_error(f'starting host with {desc} `{target}`', e)
        return 1


def start_file(file: str) -> int:
    return start('file', file, cls_from_file)


def start_cls(cls: str) -> int:
    return start('class', cls, cls_from_path)


def start_config(mod: str, name: str) -> int:
    def error(msg: ImportFailure) -> None:
        log().error(str(msg))
    def run(config: Config) -> None:
        class Plug(AutoPlugin, config=config, pname=config.name, prefix=config.prefix):
            def __init__(self, vim: Nvim) -> None:
                super().__init__(vim, config)
        start_host((config.name, Plug), True, PluginHost)
    try:
        Either.import_name(mod, name).cata(error, run)
        return 0
    except Exception as e:
        log().caught_exception_error(f'starting host from config', e)
        return 1


__all__ = ('start_host', 'start_file', 'start_cls')
