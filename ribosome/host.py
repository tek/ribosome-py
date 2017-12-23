from typing import TypeVar, Type, Callable, Any
from types import ModuleType

from neovim.msgpack_rpc import MsgpackStream, AsyncSession, Session
from neovim.api import Nvim
from neovim.msgpack_rpc.event_loop.base import BaseEventLoop
from neovim.msgpack_rpc.event_loop.uv import UvEventLoop
from neovim import attach

from amino import Either, _, L, Maybe, amino_log, Logger, __, Path, Map, List, Boolean, Nil, Just, env
from amino.either import ImportFailure
from amino.func import Val
from amino.logging import amino_root_file_logging
from amino.do import do, Do
from amino.dat import Dat
from amino.algebra import Algebra
from amino.boolean import false
from amino.util.string import decode
from amino.mod import instance_from_module, cls_from_module

from ribosome import NvimPlugin
from ribosome import options
from ribosome.config import Config
from ribosome.dispatch.data import Legacy, SendMessage, Trans, Internal, DispatchSync, DispatchAsync, Dispatch, DIO
from ribosome.dispatch.execute import execute_dispatch_job, request_result
from ribosome.dispatch.resolve import ComponentResolver
from ribosome.dispatch.run import DispatchJob
from ribosome.logging import ribo_log, nvim_logging
from ribosome.nvim import NvimFacade, NvimIO
from ribosome.plugin import plugin_class_from_config
from ribosome.plugin_state import PluginState, PluginStateHolder, DispatchConfig
from ribosome.request.handler.dispatcher import MsgDispatcher
from ribosome.request.handler.handler import RequestHandler
from ribosome.request.rpc import rpc_handler_functions, define_handlers, RpcHandlerSpec
from ribosome.nvim.io import NS
from ribosome.trans.handler import TransComplete
from ribosome.trans.internal import internal_dispatchers

Loop = TypeVar('Loop', bound=BaseEventLoop)
NP = TypeVar('NP', bound=NvimPlugin)
D = TypeVar('D')
B = TypeVar('B')
C = TypeVar('C', bound=Config)
R = TypeVar('R')
DP = TypeVar('DP', bound=Dispatch)
RDP = TypeVar('RDP', bound=Algebra)


class HostConfig(Dat['HostConfig']):

    def __init__(
            self,
            config: DispatchConfig,
            plugin_class: Maybe[Type[NP]],
    ) -> None:
        self.config = config
        self.plugin_class = plugin_class

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def dispatch(self) -> List[Dispatch]:
        return self.config.dispatch

    @property
    def specs(self) -> List[RpcHandlerSpec]:
        return self.config.specs

    @property
    def distinct_specs(self) -> List[RpcHandlerSpec]:
        return self.config.distinct_specs


def dispatch_job(sync: bool,
                 dispatches: Map[str, RDP],
                 state: PluginStateHolder[D],
                 name: str,
                 prefix: str,
                 args: tuple) -> DispatchJob:
    decoded_args = decode(args)
    fun_args = decoded_args.head | Nil
    bang = decoded_args.lift(1).contains(1)
    return DispatchJob(dispatches, state, decode(name), fun_args, sync, prefix, bang)


def request_handler(vim: NvimFacade,
                    sync: bool,
                    dispatches: Map[str, RDP],
                    state: PluginStateHolder[D],
                    config: DispatchConfig) -> Callable[[str, tuple], Any]:
    sync_prefix = '' if sync else 'a'
    def handle(name: str, args: tuple) -> Do:
        try:
            job = dispatch_job(sync, dispatches, state, name, config.prefix, args)
            amino_log.debug(f'dispatching {sync_prefix}sync request: {job.name}({job.args})')
            result = request_result(job, execute_dispatch_job(job).result(vim))
            if sync:
                ribo_log.debug(f'request `{job.name}` completed: {result}')
            return vim.encode_vim_data(result)
        except Exception as e:
            amino_log.caught_exception(f'dispatching request: {name}({args})', e)
            ribo_log.error(f'fatal error dispatching request {name}({args})')
    return handle


@do(NvimIO[PluginState[D]])
def init_state(host_config: HostConfig) -> Do:
    dispatch_config = host_config.config
    data = dispatch_config.config.state()
    components = yield ComponentResolver(dispatch_config.config).run
    plugin = yield NvimIO.delay(host_config.plugin_class)
    log_handler = yield NvimIO.delay(nvim_logging)
    yield NvimIO.pure(PluginState.cons(dispatch_config, data, plugin, components, log_handler=Just(log_handler)))


# TODO can vim be injected into each request handling process?
# irrelevant if separate channel for NvimFacade is possible
@do(NvimIO[int])
def run_session(session: Session, host_config: HostConfig) -> Do:
    yield define_handlers(host_config.distinct_specs, host_config.name, host_config.name)
    state = yield init_state(host_config)
    holder = PluginStateHolder.concurrent(state)
    ribo_log.debug(f'running session with state {state}')
    yield NvimIO.delay(
        lambda vim:
        session.run(
            request_handler(vim, True, host_config.config.sync_dispatch, holder, host_config.config),
            request_handler(vim, False, host_config.config.async_dispatch, holder, host_config.config)
        )
    )
    yield NvimIO.pure(0)


def no_listen_address(err: Exception) -> None:
    raise Exception('could not connect to the vim server from within the host')


def run_loop(session: Session, prefix: str, host_config: HostConfig) -> int:
    # sock = env['NVIM_LISTEN_ADDRESS'].value_or(no_listen_address)
    # nvim = attach('socket', path=sock)
    # vim = NvimFacade(nvim, host_config.name)
    vim = NvimFacade(Nvim.from_session(session), host_config.name)
    return run_session(session, host_config).attempt(vim).get_or_raise()


def session(*args: str, loop: Loop=UvEventLoop, transport_type: str='stdio', **kwargs: str) -> Session:
    return Session(AsyncSession(MsgpackStream(loop(transport_type, *args, **kwargs))))


def start_host(prefix: str, host_config: HostConfig) -> int:
    return run_loop(session(), prefix, host_config)


def plugin_cls_from_module(mod: ModuleType) -> Either[str, Type[NP]]:
    return cls_from_module(mod, NvimPlugin)


def config_from_module(mod: ModuleType) -> Either[str, Type[C]]:
    return instance_from_module(mod, Config)


log_initialized = False


def nvim_log() -> Logger:
    global log_initialized
    if not log_initialized:
        NvimFacade.stdio_with_logging('ribosome_start_host')
        log_initialized = True
    return ribo_log


def plugin_class_dispatchers(cls: Type[NP]) -> List[DispatchSync]:
    return rpc_handler_functions(cls) / Legacy


def config_dispatchers(config: Config) -> List[DispatchAsync]:
    def choose(name: str, handler: RequestHandler) -> DispatchAsync:
        tpe = (
            SendMessage
            if isinstance(handler.dispatcher, MsgDispatcher) else
            Internal
            if handler.internal else
            Trans
        )
        return tpe(handler)
    return config.request_handlers.handlers.map2(choose)


def host_config_1(
        config: Config,
        cls: Type[NP],
        debug: Boolean,
        io_executor: Callable[[DIO], NS[PluginState[D], TransComplete]]=None,
) -> HostConfig:
    name = config.name
    cls_dispatchers = plugin_class_dispatchers(cls)
    cfg_dispatchers = config_dispatchers(config)
    int_dispatchers = internal_dispatchers(config)
    with_method = lambda ds: Map(ds.map(lambda d: (d.spec(config.name, config.prefix).rpc_method(name), d)))
    dispatches = int_dispatchers + cfg_dispatchers + cls_dispatchers
    sync_dispatch, async_dispatch = dispatches.filter(_.sync), dispatches.filter(_.async)
    dispatch_config = DispatchConfig.cons(config, with_method(sync_dispatch), with_method(async_dispatch), io_executor)
    return HostConfig(dispatch_config, cls)


class SyntheticPlugin:
    pass


def host_config(
        config: Config,
        plugin_mixin: Either[str, Type[NP]],
        debug: Boolean=false,
        io_executor: Callable[[DIO], NS[PluginState[D], TransComplete]]=None,
) -> HostConfig:
    sup = plugin_mixin | Val(SyntheticPlugin)
    cls = plugin_class_from_config(config, sup, debug)
    return host_config_1(config, cls, debug, io_executor)


def start_config_stage_2(sup: Either[str, Type[NP]], config: Config) -> int:
    debug = options.development.exists
    amino_log.debug(f'starting plugin from {config}, debug: {debug}')
    return start_host(config.name, host_config(config, sup, debug))


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
