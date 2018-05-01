from typing import TypeVar, Callable, Any

from neovim.msgpack_rpc import MsgpackStream, AsyncSession, Session
from neovim.api import Nvim
from neovim.msgpack_rpc.event_loop.uv import UvEventLoop

from amino import amino_log, IO
from amino.do import do, Do

from ribosome.config.config import Config
from ribosome.request.execute import execute_request
from ribosome.logging import ribo_log
from ribosome.nvim.api.data import NvimApi, NativeNvimApi
from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.variable import variable_set_prefixed
from ribosome.nvim.io.api import N
from ribosome.data.plugin_state_holder import PluginStateHolder
from ribosome.rpc.state import prepare_plugin

D = TypeVar('D')
DIO = TypeVar('DIO')
B = TypeVar('B')
C = TypeVar('C', bound=Config)
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


@do(NvimIO[int])
def run_session(session: Session, config: Config) -> Do:
    holder = yield prepare_plugin(config)
    yield N.from_io(IO.delay(session._enqueue_notification, 'function:internal_init', ()))
    yield variable_set_prefixed('started', True)
    ribo_log.debug(f'running session')
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


def session(*args: str, transport_type: str='stdio', **kwargs: str) -> Session:
    return Session(AsyncSession(MsgpackStream(UvEventLoop(transport_type, *args, **kwargs))))


def connect_nvim(name: str) -> NativeNvimApi:
    return NativeNvimApi(name, Nvim.from_session(session())._session)


__all__ = ('connect_nvim', 'run_session')
