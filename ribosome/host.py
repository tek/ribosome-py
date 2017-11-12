from typing import TypeVar, Type, Callable, Generator, Any, Tuple
from types import ModuleType
from threading import Lock

from neovim.msgpack_rpc import MsgpackStream, AsyncSession, Session
from neovim.api import Nvim, walk, decode_if_bytes
from neovim.msgpack_rpc.event_loop.base import BaseEventLoop
from neovim.msgpack_rpc.event_loop.uv import UvEventLoop

import amino
from amino import Either, _, L, Maybe, Lists, amino_log, Logger, __, Path, Map, List, Boolean, Nil
from amino.either import ImportFailure
from amino.func import Val
from amino.logging import amino_root_file_logging
from amino.do import tdo
from amino.dispatch import dispatch_alg
from amino.util.exception import format_exception
from amino.boolean import true, false
from amino.dat import Dat

from ribosome.nvim import NvimFacade, NvimIO
from ribosome.logging import ribo_log
from ribosome.rpc import rpc_handler_functions, define_handlers, RpcHandlerSpec
from ribosome import NvimPlugin, AutoPlugin
from ribosome.config import Config
from ribosome import options
from ribosome.plugin import plugin_class_from_config
from ribosome.machine.process_messages import PrioQueue
from ribosome.request.dispatch import (DispatchJob, Dispatch, RunDispatch, invalid_dispatch, PluginStateHolder,
                                       PluginState, Legacy, SendMessage, Trans, DispatchResult, Internal)
from ribosome.request.handler import MsgDispatcher, RequestHandler, Full
from ribosome.machine.message_base import Message
from ribosome.machine.loop import process_message
from ribosome.machine.transition import TransitionResult, TransitionLog
from ribosome.record import encode_json_compat
from ribosome.machine.root import ComponentResolver
from ribosome.machine.send_message import send_message
from ribosome.machine import trans
from ribosome.machine.messages import ShowLogInfo, UpdateState
from ribosome.machine.scratch import Mapping

Loop = TypeVar('Loop', bound=BaseEventLoop)
NP = TypeVar('NP', bound=NvimPlugin)
D = TypeVar('D')
AS = TypeVar('AS')
A = TypeVar('A', bound=AS)
B = TypeVar('B')
C = TypeVar('C', bound=Config)
R = TypeVar('R')


class HostConfig(Dat['HostConfig']):

    def __init__(
            self,
            sync_dispatch: Map[str, Dispatch],
            async_dispatch: Map[str, Dispatch],
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


def run_dispatch(state: PluginState, args: List[Any], dispatch: Dispatch) -> NvimIO[Tuple[Any, D]]:
    amino_log.debug(f'running dispatch {dispatch}({args})')
    return dispatch_alg(RunDispatch(state, args), Dispatch, '', invalid_dispatch)(dispatch)


# TODO check how long-running messages can be handled; timeout for acquire is 10s
@tdo(NvimIO[R])
def dispatch_step(state: PluginStateHolder,
                  action: Callable[[PluginState], NvimIO[B]],
                  update: Callable[[PluginState, B], Tuple[Any, PluginState]]) -> Generator:
    def release(error: Any) -> NvimIO[R]:
        state.release()
    yield NvimIO(lambda v: state.acquire())
    result = yield action(state.state).error_effect(release)
    response, new_state = yield NvimIO(lambda v: update(state.state, result)).error_effect(release)
    yield NvimIO(lambda v: state.update(new_state)).error_effect(release)
    yield NvimIO(release)
    yield NvimIO.pure(response)


def dispatch_request_sync(job: DispatchJob, dispatch: Dispatch) -> NvimIO[Any]:
    def send(state: PluginState) -> NvimIO[Tuple[Any, D]]:
        return run_dispatch(state, job.args, dispatch)
    def update(state: PluginState, result: DispatchResult) -> Tuple[D, Any]:
        response, new_state, nil = result
        return response, new_state
    return dispatch_step(job.state, send, update)


def request_error(job: DispatchJob, exc: Exception) -> int:
    sync_prefix = '' if job.sync else 'a'
    desc = f'{sync_prefix}sync request {job.name}({job.args}) to `{job.plugin_name}`'
    tb = format_exception(exc).join_lines
    ribo_log.error(f'fatal error in {desc}')
    exc_logger = ribo_log.error if amino.development else ribo_log.debug
    exc_logger(f'{desc} failed:\n{tb}')
    return 1


@tdo(NvimIO[Any])
def resend_loop(holder: PluginStateHolder) -> Generator:
    def send(state: PluginState) -> NvimIO[Tuple[PrioQueue[Message], TransitionResult]]:
        return NvimIO(lambda v: process_message(state.messages, state, send_message))
    def update(state: PluginState, result: Tuple[PrioQueue[Message], TransitionResult]) -> Tuple[Any, PluginState]:
        messages, trs = result
        log, tr = trs.run(TransitionLog.empty)._value()
        return None, state.log(log).update(tr.data).copy(messages=messages).enqueue(tr.resend + tr.pub)
    yield dispatch_step(holder, send, update)
    yield resend_loop(holder) if holder.has_messages else NvimIO.pure(None)


@tdo(NvimIO[Any])
def dispatch_async_loop(holder: PluginStateHolder, args: List[Any], dispatch: Dispatch) -> Generator:
    def run(state: PluginState) -> NvimIO[Tuple[Any, D]]:
        return run_dispatch(state, args, dispatch)
    def update(state: PluginStateHolder, result: DispatchResult) -> Tuple[Any, PluginState]:
        response, new_state, messages = result
        return None, new_state.enqueue(messages)
    yield dispatch_step(holder, run, update)
    yield resend_loop(holder)


def dispatch_request_async(job: DispatchJob, dispatch: Dispatch) -> NvimIO[None]:
    def run(vim: NvimFacade) -> None:
        dispatch_async_loop(job.state, job.args, dispatch).attempt(vim).lmap(L(request_error)(job, _))
    return NvimIO.fork(run)


@tdo(NvimIO[Any])
def dispatch_request(job: DispatchJob) -> Generator:
    dispatch = yield NvimIO.from_maybe(job.dispatches.lift(job.name), 'no handler')
    relay = dispatch_request_sync if dispatch.sync else dispatch_request_async
    yield relay(job, dispatch)


def request_handler(
        vim: NvimFacade,
        sync: bool,
        dispatches: Map[str, Dispatch],
        state: PluginStateHolder[D, NP],
        config: Config,
) -> Callable[[str, tuple], Any]:
    sync_prefix = '' if sync else 'a'
    def handle(name: str, args: tuple) -> Generator:
        decoded_name = vim.decode_vim_data(name)
        decoded_args = Lists.wrap(walk(decode_if_bytes, args))
        fun_args = decoded_args.head | Nil
        bang = decoded_args.lift(1).contains(1)
        job = DispatchJob(dispatches, state, decoded_name, fun_args, sync, vim.prefix, bang)
        amino_log.debug(f'dispatching {sync_prefix}sync request: {decoded_name}({decoded_args})')
        result = (
            dispatch_request(job)
            .attempt(vim)
            .value_or(L(request_error)(job, _))
        )
        return vim.encode_vim_data(result)
    return handle


@tdo(NvimIO[int])
def run_session(session: Session, host_config: HostConfig) -> Generator:
    yield define_handlers(host_config.specs, host_config.name, host_config.name)
    vim = yield NvimIO(lambda a: a)
    data = host_config.config.state(vim)
    components = yield ComponentResolver(host_config.config).run
    state = PluginState.cons(vim, data, host_config.plugin_class(vim, data), components, PrioQueue.empty)
    holder = PluginStateHolder(state, Lock())
    yield NvimIO(
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


@tdo(Either[str, A])
def instance_from_module(mod: ModuleType, pred: Callable[[Any], bool], desc: str) -> Generator:
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


def plugin_class_dispatchers(cls: Type[NP]) -> List[Dispatch]:
    return rpc_handler_functions(cls) / Legacy


def config_dispatchers(config: Config) -> List[Dispatch]:
    def choose(name: str, handler: RequestHandler) -> Dispatch:
        return SendMessage(handler) if isinstance(handler.dispatcher, MsgDispatcher) else Trans(name, handler)
    return config.request_handlers.handlers.map2(choose)


@trans.plain(trans.result)
def message_log(machine: Any, state: PluginState, args: Any) -> List[str]:
    return state.message_log // encode_json_compat


message_log_handler = RequestHandler.trans_function(message_log)('message_log', Full(), true)
show_log_info_handler = RequestHandler.msg_cmd(ShowLogInfo)('show_log_info', Full(), false)
update_state_handler = RequestHandler.json_msg_cmd(UpdateState)('update_state', Full(), false)
mapping_handler = RequestHandler.msg_fun(Mapping)('mapping', Full(), false)


def internal_dispatchers(config: Config) -> List[Dispatch]:
    return List(
        Internal(message_log_handler),
        SendMessage(show_log_info_handler),
        SendMessage(update_state_handler),
        SendMessage(mapping_handler),
    )


def host_config_1(config: Config, cls: Type[NP], debug: Boolean) -> HostConfig:
    name = config.name
    cls_dispatchers = plugin_class_dispatchers(cls)
    cfg_dispatchers = config_dispatchers(config)
    int_dispatchers = internal_dispatchers(config)
    with_method = lambda ds: Map(ds.map(lambda d: (d.spec(config.name, config.prefix).rpc_method(name), d)))
    sync_dispatch, async_dispatch = (cls_dispatchers + cfg_dispatchers + int_dispatchers).split(_.sync)
    return HostConfig(with_method(sync_dispatch), with_method(async_dispatch), config, cls)


def host_config(config: Config, sup: Type[NP], debug: Boolean) -> HostConfig:
    cls = plugin_class_from_config(config, sup, debug)
    return host_config_1(config, cls, debug)


def start_config_stage_2(cls: Either[str, Type[NP]], config: Config) -> int:
    sup = cls | Val(AutoPlugin)
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
