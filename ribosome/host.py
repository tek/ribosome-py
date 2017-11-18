from typing import TypeVar, Type, Callable, Generator, Any, Tuple, Generic
from types import ModuleType
from threading import Lock

from neovim.msgpack_rpc import MsgpackStream, AsyncSession, Session
from neovim.api import Nvim
from neovim.msgpack_rpc.event_loop.base import BaseEventLoop
from neovim.msgpack_rpc.event_loop.uv import UvEventLoop

import amino
from amino import Either, _, L, Maybe, Lists, amino_log, Logger, __, Path, Map, List, Boolean, Nil
from amino.either import ImportFailure
from amino.func import Val
from amino.logging import amino_root_file_logging
from amino.do import do
from amino.dispatch import dispatch_alg
from amino.util.exception import format_exception
from amino.dat import Dat
from amino.algebra import Algebra

from ribosome.nvim import NvimFacade, NvimIO
from ribosome.logging import ribo_log
from ribosome.rpc import rpc_handler_functions, define_handlers, RpcHandlerSpec
from ribosome import NvimPlugin
from ribosome.config import Config
from ribosome import options
from ribosome.plugin import plugin_class_from_config
from ribosome.machine.process_messages import PrioQueue
from ribosome.machine.message_base import Message
from ribosome.machine.loop import process_message
from ribosome.machine.transition import TransitionResult
from ribosome.record import encode_json_compat
from ribosome.machine.root import ComponentResolver
from ribosome.machine.send_message import send_message
from ribosome.machine import trans
from ribosome.machine.messages import ShowLogInfo, UpdateState
from ribosome.machine.scratch import Mapping
from ribosome.request.handler.dispatcher import MsgDispatcher
from ribosome.request.handler.handler import RequestHandler
from ribosome.request.handler.prefix import Full
from ribosome.nvim.io import NvimIOState
from ribosome.request.dispatch.run import DispatchJob, RunDispatchSync, RunDispatchAsync, invalid_dispatch
from ribosome.request.dispatch.data import (Legacy, SendMessage, Trans, Internal, DispatchError, DispatchReturn,
                                            DispatchUnit, DispatchOutput, DispatchSync, DispatchAsync, DispatchResult,
                                            Dispatch, DispatchIO, IODIO, DIO)
from ribosome.plugin_state import PluginState, PluginStateHolder

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

    # @property
    # def dispatch(self) -> List[Dispatch]:
    #     return self.sync_dispatch.v + self.async_dispatch.v

    @property
    def specs(self) -> List[RpcHandlerSpec]:
        return self.dispatch / __.spec(self.config.name, self.config.prefix)


# def run_dispatch(state: PluginState[D, NP], args: List[Any], dispatch: Dispatch, runner: Type[RunDispatch]
#                  ) -> NvimIO[Tuple[Any, D]]:
#     amino_log.debug(f'running dispatch {dispatch}({args})')
#     return dispatch_alg(Runner(state, args), Dispatch, '', invalid_dispatch)(dispatch)


class ExecuteDispatchIO:

    def i_o_dio(self, io: IODIO[A]) -> NvimIO[Any]:
        return


execute_io = dispatch_alg(ExecuteDispatchIO(), DIO, '')


class ExecuteDispatchOutput:

    def dispatch_error(self, result: DispatchError) -> NvimIO[Any]:
        return result.exception / NvimIO.exception | NvimIO(lambda v: ribo_log.error(result.message))

    def dispatch_return(self, result: DispatchReturn) -> NvimIO[Any]:
        return NvimIO.pure(result.value)

    def dispatch_unit(self, result: DispatchUnit) -> NvimIO[Any]:
        return NvimIO.pure(0)

    def dispatch_io(self, result: DispatchIO) -> NvimIO[Any]:
        return execute_io(result)


execute_output = dispatch_alg(ExecuteDispatchOutput(), DispatchOutput, '')


# TODO check how long-running messages can be handled; timeout for acquire is 10s
@do(NvimIO[R])
def dispatch_step(holder: PluginStateHolder,
                  action: Callable[[], NvimIOState[PluginState[D, NP], B]],
                  update: Callable[[B], NvimIOState[PluginState[D, NP], Any]]) -> Generator:
    def release(error: Any) -> NvimIO[R]:
        holder.release()
    yield NvimIO(lambda v: holder.acquire())
    state1, response = yield action().run(holder.state).error_effect(release)
    print(response)
    state2, result = yield update(response).run(state1).error_effect(release)
    print(result)
    yield NvimIO(lambda v: holder.update(state2)).error_effect(release)
    r = yield execute_output(result.output)
    yield NvimIO(release)
    yield NvimIO.pure(r)


class DispatchRunner(Generic[RDP]):

    @staticmethod
    def cons(run: Type[RDP], dp: Type[DP]) -> 'DispatchRunner[RDP]':
        return DispatchRunner(lambda args: dispatch_alg(run(args), dp, '', invalid_dispatch))

    def __init__(self, f: Callable[[tuple], Callable[[RDP], NvimIOState[PluginState[D, NP], DispatchOutput]]]) -> None:
        self.f = f

    def __call__(self, args: tuple) -> Callable[[RDP], NvimIOState[PluginState[D, NP], DispatchOutput]]:
        return self.f(args)


def execute(job: DispatchJob, dispatch: DP, runner: DispatchRunner[RDP]) -> NvimIO[Any]:
    def send() -> NvimIOState[PluginState[D, NP], DispatchResult]:
        return runner(job.args)(dispatch)
    return dispatch_step(job.state, send, NvimIOState.pure)


# unconditionally fork a resend loop in case the sync transition has returned messages
# only allow the first transition to provide a return value
def execute_sync(job: DispatchJob, dispatch: DispatchSync) -> NvimIO[Any]:
    return execute(job, dispatch, DispatchRunner.cons(RunDispatchSync, DispatchSync))


def request_error(job: DispatchJob, exc: Exception) -> int:
    sync_prefix = '' if job.sync else 'a'
    desc = f'{sync_prefix}sync request {job.name}({job.args}) to `{job.plugin_name}`'
    tb = format_exception(exc).join_lines
    ribo_log.error(f'fatal error in {desc}')
    exc_logger = ribo_log.error if amino.development else ribo_log.debug
    exc_logger(f'{desc} failed:\n{tb}')
    return 1


# maybe don't enqueue messages here, but in `execute_output`
@do(NvimIO[Any])
def resend_loop(holder: PluginStateHolder) -> Generator:
    def send() -> NvimIOState[PluginState[D, NP], Tuple[PrioQueue[Message], TransitionResult]]:
        return NvimIOState.inspect(lambda state: process_message(state.messages, state, send_message))
    @do(NvimIOState[PluginState[D, NP], Tuple[PrioQueue[Message], TransitionResult]])
    def update(result: Tuple[PrioQueue[Message], TransitionResult]) -> Generator:
        messages, trs = result
        tr = yield trs
        # yield NvimIOState.modify(__.log(log))
        # yield NvimIOState.modify(__.update(tr.data))
        yield NvimIOState.modify(__.copy(messages=messages))
        # yield NvimIOState.modify(__.enqueue(tr.resend + tr.pub))
        yield NvimIOState.pure(tr)
    yield dispatch_step(holder, send, update)
    yield resend_loop(holder) if holder.has_messages else NvimIO.pure(None)


@do(NvimIO[Any])
def execute_async_loop(job: DispatchJob, dispatch: DispatchAsync) -> Generator:
    yield execute(job, dispatch, DispatchRunner.cons(RunDispatchAsync, DispatchAsync))
    yield resend_loop(job.state)


def execute_async(job: DispatchJob, dispatch: DispatchAsync) -> NvimIO[None]:
    def run(vim: NvimFacade) -> None:
        execute_async_loop(job, dispatch).attempt(vim).lmap(L(request_error)(job, _))
    return NvimIO.fork(run)


@do(NvimIO[Any])
def execute_dispatch_job(job: DispatchJob) -> Generator:
    dispatch = yield NvimIO.from_maybe(job.dispatches.lift(job.name), 'no handler')
    relay = execute_sync if dispatch.sync else execute_async
    yield relay(job, dispatch)


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
    def handle(name: str, args: tuple) -> Generator:
        job = dispatch_job(vim, sync, dispatches, state, name, args)
        amino_log.debug(f'dispatching {sync_prefix}sync request: {job.name}({job.args})')
        result = (
            execute_dispatch_job(job)
            .attempt(vim)
            .value_or(L(request_error)(job, _))
        )
        return vim.encode_vim_data(result)
    return handle


@do(NvimIO[int])
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


@do(Either[str, A])
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


def plugin_class_dispatchers(cls: Type[NP]) -> List[DispatchSync]:
    return rpc_handler_functions(cls) / Legacy


def config_dispatchers(config: Config) -> List[DispatchAsync]:
    def choose(name: str, handler: RequestHandler) -> DispatchAsync:
        return SendMessage(handler) if isinstance(handler.dispatcher, MsgDispatcher) else Trans(name, handler)
    return config.request_handlers.handlers.map2(choose)


@trans.plain(trans.result)
def message_log(machine: Any, state: PluginState[D, NP], args: Any) -> List[str]:
    return state.message_log // encode_json_compat


message_log_handler = RequestHandler.trans_function(message_log)('message_log', Full())
show_log_info_handler = RequestHandler.msg_cmd(ShowLogInfo)('show_log_info', Full())
update_state_handler = RequestHandler.json_msg_cmd(UpdateState)('update_state', Full())
mapping_handler = RequestHandler.msg_fun(Mapping)('mapping', Full())
# nvim_io_handler = RequestHandler.internal(RunNvimIOAlg, run_nvim_io)


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
