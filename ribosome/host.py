from typing import TypeVar, Type, Callable, Any
from types import ModuleType

from neovim.msgpack_rpc import MsgpackStream, AsyncSession, Session
from neovim.api import Nvim
from neovim.msgpack_rpc.event_loop.base import BaseEventLoop
from neovim.msgpack_rpc.event_loop.uv import UvEventLoop

from amino import Either, _, L, amino_log, Logger, __, Path, Nil, Just, IO
from amino.either import ImportFailure
from amino.logging import amino_root_file_logging
from amino.do import do, Do
from amino.mod import instance_from_module

from ribosome.config.config import Config
from ribosome.request.execute import execute_request
from ribosome.logging import ribo_log, nvim_logging
from ribosome.nvim.api.data import NvimApi, NativeNvimApi
from ribosome.data.plugin_state import PluginState
from ribosome.config.settings import Settings
from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.variable import variable_set_prefixed
from ribosome.nvim.io.api import N
from ribosome.data.plugin_state_holder import PluginStateHolder
from ribosome.nvim.io.state import NS
from ribosome.config.component import ComponentConfig
from ribosome.components.internal.update import init_rpc
from ribosome.compute.output import ProgOutput
from ribosome.compute.prog import Prog
from ribosome.compute.interpret import ProgIOInterpreter
from ribosome.compute.program import Program

Loop = TypeVar('Loop', bound=BaseEventLoop)
D = TypeVar('D')
DIO = TypeVar('DIO')
B = TypeVar('B')
C = TypeVar('C', bound=Config)
S = TypeVar('S', bound=Settings)
CC = TypeVar('CC')
R = TypeVar('R')


def request_handler(vim: NvimApi, sync: bool, state: PluginStateHolder[D]) -> Callable[[str, tuple], Any]:
    def handle(name: str, args: tuple) -> Any:
        try:
            return execute_request(vim, state, name, args, sync)
        except Exception as e:
            desc = f'dispatching request {name}({args})'
            amino_log.caught_exception(desc, e)
            ribo_log.error(f'fatal error {desc}')
    return handle


@do(NvimIO[PluginState[S, D, CC]])
def init_state(config: Config, io_interpreter: ProgIOInterpreter=None, logger: Program[None]=None) -> Do:
    data = config.basic.state_ctor()
    log_handler = yield N.delay(nvim_logging)
    state = PluginState.cons(
        config.basic,
        ComponentConfig(config.components),
        config.request_handlers,
        data,
        Nil,
        config.init,
        logger=logger,
        io_interpreter=io_interpreter,
        log_handler=log_handler,
    )
    yield init_rpc().run_s(state)


@do(NvimIO[int])
def run_session(session: Session, config: Config) -> Do:
    state = yield init_state(config)
    holder = PluginStateHolder.concurrent(state)
    ribo_log.debug(f'running session')
    yield N.from_io(IO.delay(session._enqueue_notification, 'function:internal_init', ()))
    yield variable_set_prefixed('started', True)
    yield N.delay(
        lambda vim:
        session.run(
            request_handler(vim, True, holder),
            request_handler(vim, False, holder)
        )
    )
    yield N.pure(0)


def no_listen_address(err: Exception) -> None:
    raise Exception('could not connect to the vim server from within the host')


def session(*args: str, loop: Type[Loop]=UvEventLoop, transport_type: str='stdio', **kwargs: str) -> Session:
    return Session(AsyncSession(MsgpackStream(loop(transport_type, *args, **kwargs))))


def connect_nvim(name: str) -> NvimApi:
    return NativeNvimApi(name, Nvim.from_session(session())._session)


def run_loop(session: Session, config: Config) -> int:
    amino_log.debug(f'starting plugin from {config.basic}')
    vim = connect_nvim(config.basic.name)
    return run_session(vim.session, config).unsafe(vim)


def config_from_module(mod: ModuleType) -> Either[str, Type[C]]:
    return instance_from_module(mod, Config)


log_initialized = False


def nvim_stdio_with_logging(name: str) -> NvimApi:
    from ribosome.logging import nvim_logging
    vim = NativeNvimApi(name, session())
    nvim_logging(vim)
    return vim


def nvim_log() -> Logger:
    global log_initialized
    if not log_initialized:
        nvim_stdio_with_logging('ribosome_start_host')
        log_initialized = True
    return ribo_log


def config(config: Config) -> Config:
    return Config.cons(config.basic.name, config.state_ctor)


def error(msg: str) -> int:
    try:
        amino_log.error(msg)
        nvim_log().error(msg)
    except Exception as e:
        pass
    return 1


def import_error(e: ImportFailure, desc: str) -> int:
    return error(e.expand.join_lines)


def exception(e: Exception, desc: str) -> int:
    f = __.caught_exception_error(f'starting host from {desc}', e)
    try:
        f(amino_log)
        f(nvim_log())
    except Exception as e:
        pass
    return 1


def start_config_stage_1(mod: ModuleType) -> int:
    return config_from_module(mod).cata(error, run_loop)


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
