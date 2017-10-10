import functools
from typing import TypeVar, Type, Callable, Tuple, Generator, Any
from types import ModuleType

from neovim.msgpack_rpc import MsgpackStream, AsyncSession, Session
from neovim.plugin import Host
from neovim.api import Nvim
from neovim.msgpack_rpc.event_loop.base import BaseEventLoop
from neovim.msgpack_rpc.event_loop.asyncio import AsyncioEventLoop
from neovim.msgpack_rpc.event_loop.uv import UvEventLoop

from amino import Either, _, L, Maybe, Lists, amino_log, Logger, __, Path
from amino.either import ImportFailure
from amino.func import Val
from amino.logging import amino_root_file_logging
from amino.do import tdo

from ribosome.nvim import NvimFacade
from ribosome.logging import ribo_log, Logging
from ribosome.rpc import rpc_handler_functions, RpcHandlerFunction, define_handlers
from ribosome import NvimPlugin, AutoPlugin
from ribosome.settings import Config
from ribosome import options
from ribosome.plugin import plugin_class_from_config

Loop = TypeVar('Loop', bound=BaseEventLoop)
NP = TypeVar('NP', bound=NvimPlugin)
D = TypeVar('D')
AS = TypeVar('AS')
A = TypeVar('A', bound=AS)
C = TypeVar('C', bound=Config)


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


def start_host(prefix: str, tpe: Type[NP], uv_loop: bool) -> int:
    Loop = UvEventLoop if uv_loop else AsyncioEventLoop
    host(Loop).start((prefix, tpe))
    return 0


@tdo(Either[str, A])
def instance_from_module(mod: ModuleType, pred: Callable[[Any], bool], desc: str) -> Generator:
    all = yield Maybe.getattr(mod, '__all__').to_either(f'module `{mod.__name__}` does not define `__all__`')
    yield (
        Lists.wrap(all)
        .flat_map(L(Maybe.getattr)(mod, _))
        .find(pred)
        .to_either(f'no {desc} in ``{mod.__name__}.__all__`')
    )


def cls_from_module(mod: ModuleType, tpe: Type[AS]) -> Either[str, Type[A]]:
    pred = lambda a: isinstance(a, type) and issubclass(a, tpe)
    return instance_from_module(mod, pred, f'subclass of `{tpe}`')


def plugin_cls_from_module(mod: ModuleType) -> Either[str, Type[NP]]:
    return cls_from_module(mod, NvimPlugin)


def config_from_module(mod: ModuleType) -> Either[str, Type[C]]:
    pred = lambda a: isinstance(a, Config)
    return instance_from_module(mod, pred, 'instance of `Config`')


log_initialized = False


def nvim_log() -> Logger:
    global log_initialized
    if not log_initialized:
        NvimFacade.stdio_with_logging('ribosome_start_host')
        log_initialized = True
    return ribo_log


def start_config_stage_2(cls: Either[str, Type[NP]], config: Config) -> int:
    sup = cls | Val(AutoPlugin)
    debug = options.development.exists
    amino_log.debug(f'starting plugin from {config} with superclass {sup}, debug: {debug}')
    return start_host(config.name, plugin_class_from_config(config, sup, debug), True)


def error(msg: str) -> int:
    amino_log.error(msg)
    nvim_log().error(msg)
    return 1


def import_error(e: ImportFailure, desc: str) -> int:
    return error(e.expand.join_lines)


def exception(e: Exception, desc: str) -> int:
    f = __.caught_exception_error(f'starting host from {desc}', e)
    f(amino_log)
    f(nvim_log())
    return 1


def start_config_stage_1(mod: ModuleType) -> int:
    plugin_cls = plugin_cls_from_module(mod)
    return config_from_module(mod).cata(error, L(start_config_stage_2)(plugin_cls, _))


def setup_log() -> None:
    amino_root_file_logging()


def start_from(source: str, importer: Callable[[str], Either[ImportFailure, ModuleType]], desc: str) -> int:
    try:
        setup_log()
        amino_log.debug(f'start_{desc}: {source}')
        return importer(source).cata(L(import_error)(_, source), start_config_stage_1)
    except Exception as e:
        return exception(e, source)


def start_module(mod: str) -> int:
    return start_from(mod, Either.import_module, 'module')


def start_file(path: str) -> int:
    p = Path(path)
    file = p / '__init__.py' if p.is_dir() else p
    return start_from(str(file), Either.import_file, 'file')


__all__ = ('start_host', 'start_module', 'start_file')
