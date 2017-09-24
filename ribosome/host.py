import inspect
import functools
from typing import TypeVar, Type, Callable, Tuple, Generator, Any
from types import ModuleType

from neovim.msgpack_rpc import MsgpackStream, AsyncSession, Session
from neovim.plugin import Host
from neovim.api import Nvim
from neovim.msgpack_rpc.event_loop.base import BaseEventLoop
from neovim.msgpack_rpc.event_loop.asyncio import AsyncioEventLoop
from neovim.msgpack_rpc.event_loop.uv import UvEventLoop

from amino import Either, _, L, do, Path, Maybe, Lists, Right, Try, amino_log, Logger, curried
from amino.either import ImportFailure
from amino.func import Val
from amino.logging import amino_root_file_logging

from ribosome.nvim import NvimFacade
from ribosome.logging import ribo_log, Logging
from ribosome.rpc import rpc_handler_functions, RpcHandlerFunction, define_handlers
from ribosome import NvimPlugin, AutoPlugin
from ribosome.settings import Config
from ribosome import options

Loop = TypeVar('Loop', bound=BaseEventLoop)
NP = TypeVar('NP', bound=NvimPlugin)
D = TypeVar('D')


class PluginHost(Host, Logging):

    def _load(self, data: Tuple[str, Type[NP]]) -> None:
        amino_log.debug(f'loading host with {data}')
        file, tpe = data
        name = tpe.name or 'ribosome'
        vim = NvimFacade(self._configure_nvim_for(tpe), name)
        instance = tpe(vim.vim)
        handlers = rpc_handler_functions(instance)
        specs = handlers / _.spec
        handlers % L(self.register)(file, _)
        self._specs[file] = specs / _.encode
        define_handlers(vim.channel_id, specs, name, file).attempt(vim).get_or_raise
        amino_log.debug(f'defined handlers for {file}')

    def register(self, file: str, handler: RpcHandlerFunction) -> None:
        spec = handler.spec
        method = spec.rpc_method(file)
        func = functools.partial(self._wrap_function, handler.func, spec.sync, True, None, method)
        self._copy_attributes(handler.func, func)
        target = self._request_handlers if spec.sync else self._notification_handlers
        target[method] = func
        amino_log.debug(f'registered {handler} for {file}')


def session(Loop: Loop, *args: str, transport_type: str='stdio', **kwargs: str) -> Session:
    return Session(AsyncSession(MsgpackStream(Loop(transport_type, *args, **kwargs))))


def host(loop: Loop) -> PluginHost:
    sess = session(loop)
    nvim = Nvim.from_session(sess)
    return PluginHost(nvim)


def start_host(data: Tuple[str, Type[NP]], uv_loop: bool) -> int:
    Loop = UvEventLoop if uv_loop else AsyncioEventLoop
    host(Loop).start(data)
    return 0


@do
def cls_from_file(file: str, mod: ModuleType) -> Generator[Either[str, Tuple[str, Type[NP]]], Any, None]:
    all = yield Maybe.getattr(mod, '__all__').to_either(f'file `{file}` does not define `__all__`')
    name = yield Lists.wrap(all).head.to_either(f'`{mod}.__all__` is empty')
    tpe = yield Maybe.getattr(mod, name).to_either(f'{mod}.{name} does not exist')
    yield Right((file, tpe))


@do
def cls_from_path(path: str) -> Generator[Either[str, Tuple[str, Type[NP]]], Any, None]:
    tpe = yield Either.import_path(path)
    file = yield Try(inspect.getfile, tpe)
    yield Right((file, tpe))


@do
def cls_from_module(path: str) -> Generator[Either[str, Tuple[str, Type[NP]]], Any, None]:
    mod = yield Either.import_module(path)
    file = mod.__file__
    yield cls_from_file(file, mod)


log_initialized = False


def nvim_log() -> Logger:
    global log_initialized
    if not log_initialized:
        NvimFacade.stdio_with_logging('ribosome_start_host')
        log_initialized = True
    return ribo_log


def start(desc: str, target: str, cls: Callable[[str], Either[str, Tuple[str, Type[NP]]]]) -> int:
    def error(msg: str) -> None:
        err = f'invalid rplugin {desc} `{target}`: {msg}'
        amino_log.error(err)
        nvim_log().error(err)
    try:
        amino_log.debug(f'starting rplugin {desc} `{target}`')
        cls(target).map(L(start_host)(_, True)).leffect(error)
        return 0
    except Exception as e:
        nvim_log().caught_exception_error(f'starting host with {desc} `{target}`', e)
        return 1


def start_cls(cls: str) -> int:
    return start('class', cls, cls_from_path)


def start_config_stage_1(cls: Either[str, Type[NP]], config: Config) -> int:
    sup = cls | Val(AutoPlugin)
    amino_log.debug(f'starting plugin from {config} with superclass {sup}')
    debug = options.development.exists
    class Plug(sup, config=config, pname=config.name, prefix=config.prefix, debug=debug):
        def __init__(self, vim: Nvim) -> None:
            super().__init__(vim, config)
    return start_host((config.name, Plug), True)


def setup_log() -> None:
    amino_root_file_logging()


def start_config(mod: str, name: str) -> int:
    setup_log()
    def error(msg: ImportFailure) -> int:
        s = str(msg)
        amino_log.error(s)
        nvim_log().error(s)
        return 1
    def relay(config: Config) -> int:
        cls = cls_from_module(mod) / _[1]
        return start_config_stage_1(cls, config)
    try:
        return Either.import_name(mod, name).cata(error, relay)
    except Exception as e:
        amino_log.caught_exception_error(f'starting host from config', e)
        nvim_log().caught_exception_error(f'starting host from config', e)
        return 1


def start_file(file: str) -> int:
    def read_config(mod: ModuleType) -> Maybe[Config]:
        return Maybe.getattr(mod, 'config')
    setup_log()
    def analyze_mod(mod: ModuleType) -> int:
        cls = cls_from_file(file, mod) / _[1]
        amino_log.debug(f'analyze_mod: {mod} / {cls}')
        return (
            read_config(mod)
            .cata(
                curried(start_config_stage_1)(cls),
                (lambda: start('file', file, L(cls_from_file)(_, mod)))
            )
        )
    def error(e: ImportFailure) -> None:
        amino_log.error(f'failed to import {file}: {e.expand.join_lines}')
    try:
        amino_log.debug(f'start_file: {file}')
        return Either.import_file(Path(file)).leffect(error) / analyze_mod | 1
    except Exception as e:
        nvim_log().caught_exception_error(f'starting host from file', e)
        return 1

__all__ = ('start_host', 'start_file', 'start_cls')
