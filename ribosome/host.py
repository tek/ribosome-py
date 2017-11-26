from typing import TypeVar, Type, Callable, Any
from types import ModuleType
from threading import Lock

from neovim.msgpack_rpc import MsgpackStream, AsyncSession, Session
from neovim.api import Nvim
from neovim.msgpack_rpc.event_loop.base import BaseEventLoop
from neovim.msgpack_rpc.event_loop.uv import UvEventLoop

from amino import Either, _, L, Maybe, Lists, amino_log, Logger, __, Path, Map, List, Boolean, Nil
from amino.either import ImportFailure
from amino.func import Val
from amino.logging import amino_root_file_logging
from amino.do import do, Do
from amino.dat import Dat
from amino.algebra import Algebra
from amino.state import EitherState

from ribosome import NvimPlugin
from ribosome import options
from ribosome.components.scratch import Mapping
from ribosome.config import Config
from ribosome.dispatch.data import Legacy, SendMessage, Trans, Internal, DispatchSync, DispatchAsync, Dispatch
from ribosome.dispatch.execute import execute_dispatch_job, request_error
from ribosome.dispatch.resolve import ComponentResolver
from ribosome.dispatch.run import DispatchJob
from ribosome.logging import ribo_log
from ribosome.nvim import NvimFacade, NvimIO
from ribosome.plugin import plugin_class_from_config
from ribosome.plugin_state import PluginState, PluginStateHolder
from ribosome.record import encode_json_compat
from ribosome.request.handler.dispatcher import MsgDispatcher
from ribosome.request.handler.handler import RequestHandler
from ribosome.request.handler.prefix import Full
from ribosome.request.rpc import rpc_handler_functions, define_handlers, RpcHandlerSpec
from ribosome.trans.api import trans
from ribosome.trans.messages import ShowLogInfo, UpdateState, Stage1, Quit
from ribosome.trans.queue import PrioQueue

Loop = TypeVar('Loop', bound=BaseEventLoop)
NP = TypeVar('NP', bound=NvimPlugin)
D = TypeVar('D')
AS = TypeVar('AS')
A = TypeVar('A', bound=AS)
B = TypeVar('B')
C = TypeVar('C', bound=Config)
R = TypeVar('R')
DP = TypeVar('DP', bound=Dispatch)
RDP = TypeVar('RDP', bound=Algebra)


class HostConfig(Dat['HostConfig']):

    def __init__(
            self,
            sync_dispatch: Map[str, DispatchSync],
            async_dispatch: Map[str, DispatchAsync],
            config: Config,
            plugin_class: Maybe[Type[NP]],
    ) -> None:
        self.sync_dispatch = sync_dispatch
        self.async_dispatch = async_dispatch
        self.config = config
        self.plugin_class = plugin_class

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def dispatch(self) -> List[Dispatch]:
        return self.sync_dispatch.v + self.async_dispatch.v

    @property
    def specs(self) -> List[RpcHandlerSpec]:
        return self.dispatch / __.spec(self.config.name, self.config.prefix)


def dispatch_job(vim: NvimFacade,
                 sync: bool,
                 dispatches: Map[str, RDP],
                 state: PluginStateHolder[D, NP],
                 name: str,
                 args: tuple) -> DispatchJob:
    decoded_name = vim.decode_vim_data(name)
    decoded_args = vim.decode_vim_data(args)
    fun_args = decoded_args.head | Nil
    bang = decoded_args.lift(1).contains(1)
    return DispatchJob(dispatches, state, decoded_name, fun_args, sync, vim.prefix, bang)


def request_handler(vim: NvimFacade,
                    sync: bool,
                    dispatches: Map[str, RDP],
                    state: PluginStateHolder[D, NP],
                    config: Config) -> Callable[[str, tuple], Any]:
    sync_prefix = '' if sync else 'a'
    def handle(name: str, args: tuple) -> Do:
        job = dispatch_job(vim, sync, dispatches, state, name, args)
        amino_log.debug(f'dispatching {sync_prefix}sync request: {job.name}({job.args})')
        result = (
            execute_dispatch_job(job)
            .attempt(vim)
            .value_or(L(request_error)(job, _))
        )
        if sync:
            ribo_log.debug(f'request `{job.name}` completed: {result}')
        return vim.encode_vim_data(result)
    return handle


@do(NvimIO[PluginState[D, NP]])
def init_state(host_config: HostConfig) -> Do:
    data = yield NvimIO.delay(host_config.config.state)
    components = yield ComponentResolver(host_config.config).run
    plugin = yield NvimIO.delay(lambda vim: host_config.plugin_class(vim, data))
    yield NvimIO.pure(PluginState.cons(data, plugin, components, PrioQueue.empty))


# can vim be injected into each request handling process?
@do(NvimIO[int])
def run_session(session: Session, host_config: HostConfig) -> Do:
    yield define_handlers(host_config.specs, host_config.name, host_config.name)
    state = yield init_state(host_config)
    holder = PluginStateHolder(state, Lock())
    yield NvimIO.delay(
        lambda vim:
        session.run(
            request_handler(vim, True, host_config.sync_dispatch, holder, host_config.config),
            request_handler(vim, False, host_config.async_dispatch, holder, host_config.config)
        )
    )
    yield NvimIO.pure(0)


def run_loop(session: Session, prefix: str, host_config: HostConfig) -> int:
    vim = NvimFacade(Nvim.from_session(session), host_config.name)
    return run_session(session, host_config).attempt(vim).get_or_raise()


def session(*args: str, loop: Loop=UvEventLoop, transport_type: str='stdio', **kwargs: str) -> Session:
    return Session(AsyncSession(MsgpackStream(loop(transport_type, *args, **kwargs))))


def start_host(prefix: str, host_config: HostConfig) -> int:
    return run_loop(session(), prefix, host_config)


@do(Either[str, A])
def instance_from_module(mod: ModuleType, pred: Callable[[Any], bool], desc: str) -> Do:
    all = yield Maybe.getattr(mod, '__all__').to_either(f'module `{mod.__name__}` does not define `__all__`')
    yield (
        Lists.wrap(all)
        .flat_map(L(Maybe.getattr)(mod, _))
        .find(pred)
        .to_either(f'no {desc} in `{mod.__name__}.__all__`')
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


@trans.free.result(trans.st)
@do(EitherState[PluginState[D, NP], str])
def message_log() -> Do:
    yield EitherState.inspect_f(__.message_log.traverse(encode_json_compat, Either))


message_log_handler = RequestHandler.trans_function(message_log)('message_log', Full(), sync=True)
show_log_info_handler = RequestHandler.msg_cmd(ShowLogInfo)('show_log_info', Full())
update_state_handler = RequestHandler.json_msg_cmd(UpdateState)('update_state', Full())
mapping_handler = RequestHandler.msg_fun(Mapping)('mapping', Full())
stage_1_handler = RequestHandler.msg_cmd(Stage1)('stage_1', Full())
quit_handler = RequestHandler.msg_cmd(Quit)('quit', Full())


def internal_dispatchers(config: Config) -> List[Dispatch]:
    return List(
        Internal(message_log_handler),
        SendMessage(show_log_info_handler),
        SendMessage(update_state_handler),
        SendMessage(mapping_handler),
        SendMessage(stage_1_handler),
        SendMessage(quit_handler),
    )


def host_config_1(config: Config, cls: Type[NP], debug: Boolean) -> HostConfig:
    name = config.name
    cls_dispatchers = plugin_class_dispatchers(cls)
    cfg_dispatchers = config_dispatchers(config)
    int_dispatchers = internal_dispatchers(config)
    with_method = lambda ds: Map(ds.map(lambda d: (d.spec(config.name, config.prefix).rpc_method(name), d)))
    dispatches = cls_dispatchers + cfg_dispatchers + int_dispatchers
    sync_dispatch, async_dispatch = dispatches.filter(_.sync), dispatches.filter(_.async)
    return HostConfig(with_method(sync_dispatch), with_method(async_dispatch), config, cls)


def host_config(config: Config, sup: Type[NP], debug: Boolean) -> HostConfig:
    cls = plugin_class_from_config(config, sup, debug)
    return host_config_1(config, cls, debug)


class SyntheticPlugin:
    pass


def start_config_stage_2(cls: Either[str, Type[NP]], config: Config) -> int:
    sup = cls | Val(SyntheticPlugin)
    debug = options.development.exists
    amino_log.debug(f'starting plugin from {config} with superclass {sup}, debug: {debug}')
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
    nvim_log()
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
