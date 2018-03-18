from typing import TypeVar, Type, Callable, Any
from types import ModuleType

from neovim.msgpack_rpc import MsgpackStream, AsyncSession, Session
from neovim.api import Nvim
from neovim.msgpack_rpc.event_loop.base import BaseEventLoop
from neovim.msgpack_rpc.event_loop.uv import UvEventLoop

from amino import Either, _, L, amino_log, Logger, __, Path, Nil, Just
from amino.either import ImportFailure
from amino.logging import amino_root_file_logging
from amino.do import do, Do
from amino.algebra import Algebra
from amino.util.string import decode
from amino.mod import instance_from_module

from ribosome.config.config import Config
from ribosome.dispatch.data import Dispatch
from ribosome.dispatch.execute import execute_dispatch_job, request_result
from ribosome.dispatch.run import DispatchJob
from ribosome.logging import ribo_log, nvim_logging
from ribosome.nvim import NvimFacade, NvimIO
from ribosome.plugin_state import PluginState, PluginStateHolder, DispatchConfig
from ribosome.dispatch.update import update_rpc
from ribosome.config.settings import Settings

Loop = TypeVar('Loop', bound=BaseEventLoop)
D = TypeVar('D')
B = TypeVar('B')
C = TypeVar('C', bound=Config)
R = TypeVar('R')
DP = TypeVar('DP', bound=Dispatch)
RDP = TypeVar('RDP', bound=Algebra)
S = TypeVar('S', bound=Settings)
CC = TypeVar('CC')


def dispatch_job(state: PluginStateHolder[D], name: str, args: tuple, sync: bool) -> DispatchJob:
    decoded_args = decode(args)
    fun_args = decoded_args.head | Nil
    bang = decoded_args.lift(1).contains(1)
    return DispatchJob(state, decode(name), fun_args, sync, bang)


def request_handler(
        vim: NvimFacade,
        sync: bool,
        state: PluginStateHolder[D],
) -> Callable[[str, tuple], Any]:
    sync_prefix = '' if sync else 'a'
    def handle(name: str, args: tuple) -> Any:
        try:
            job = dispatch_job(state, name, args, sync)
            amino_log.debug(f'dispatching {sync_prefix}sync request: {job.name}({job.args})')
            result = request_result(job, execute_dispatch_job(job).result(vim))
            if sync:
                ribo_log.debug(f'request `{job.name}` completed: {result}')
            return vim.encode_vim_data(result)
        except Exception as e:
            amino_log.caught_exception(f'dispatching request: {name}({args})', e)
            ribo_log.error(f'fatal error dispatching request {name}({args})')
    return handle


@do(NvimIO[PluginState[S, D, CC]])
def init_state(dispatch_config: DispatchConfig) -> Do:
    data = dispatch_config.config.state()
    log_handler = yield NvimIO.delay(nvim_logging)
    state = yield NvimIO.pure(PluginState.cons(dispatch_config, data, Nil, log_handler=Just(log_handler)))
    yield update_rpc().run_s(state)


@do(NvimIO[int])
def run_session(session: Session, dispatch_config: DispatchConfig) -> Do:
    state = yield init_state(dispatch_config)
    holder = PluginStateHolder.concurrent(state)
    ribo_log.debug(f'running session')
    yield NvimIO.delay(__.vars.set_p('started', True))
    yield NvimIO.delay(
        lambda vim:
        session.run(
            request_handler(vim, True, holder),
            request_handler(vim, False, holder)
        )
    )
    yield NvimIO.pure(0)


def no_listen_address(err: Exception) -> None:
    raise Exception('could not connect to the vim server from within the host')


def run_loop(session: Session, prefix: str, dispatch_config: DispatchConfig) -> int:
    vim = NvimFacade(Nvim.from_session(session), dispatch_config.name)
    return run_session(session, dispatch_config).attempt(vim).get_or_raise()


def session(*args: str, loop: Loop=UvEventLoop, transport_type: str='stdio', **kwargs: str) -> Session:
    return Session(AsyncSession(MsgpackStream(loop(transport_type, *args, **kwargs))))


def start_host(prefix: str, dispatch_config: DispatchConfig) -> int:
    return run_loop(session(), prefix, dispatch_config)


def config_from_module(mod: ModuleType) -> Either[str, Type[C]]:
    return instance_from_module(mod, Config)


log_initialized = False


def nvim_log() -> Logger:
    global log_initialized
    if not log_initialized:
        NvimFacade.stdio_with_logging('ribosome_start_host')
        log_initialized = True
    return ribo_log


def start_config_stage_2(config: Config) -> int:
    amino_log.debug(f'starting plugin from {config.name}')
    return start_host(config.name, DispatchConfig.cons(config))


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
    return config_from_module(mod).cata(error, start_config_stage_2)


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
