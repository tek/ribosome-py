from typing import Any, Callable, TypeVar, Tuple
import asyncio

from kallikrein import Expectation, pending, k
from kallikrein.matchers import contain
from kallikrein.matchers.either import be_right
from kallikrein.expectable import kio

from amino import List, do, Do, Map, IO, Path, Left
from amino.test import temp_file
from amino.test.spec import SpecBase
from amino.logging import module_log

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.variable import variable_set, variable_raw
from ribosome.nvim.api.command import nvim_command
from ribosome.nvim.api.rpc import channel_id
from ribosome.nvim.api.function import nvim_call_function
from ribosome.nvim.io.api import N
from ribosome.rpc.comm import Comm, RpcComm, StateGuard, exclusive_ns
from ribosome.config.config import Config
from ribosome.rpc.strict import StrictRpc
from ribosome.rpc.start import start_comm, stop_comm, plugin_execute_receive_request
from ribosome.compute.api import prog
from ribosome.nvim.io.state import NS
from ribosome.rpc.api import rpc
from ribosome.rpc.state import cons_state
from ribosome.components.internal.update import init_rpc
from ribosome.rpc.to_plugin import rpc_handler
from ribosome.rpc.nvim_api import RiboNvimApi
from ribosome.rpc.native.io import Asyncio, cons_asyncio_embed

log = module_log()
A = TypeVar('A')


def stop() -> None:
    asyncio.get_event_loop().stop()


def main_loop() -> None:
    try:
        asyncio.run_event_loop()
    except Exception as e:
        log.error(e)


value = 'successfully set variable'


@do(NvimIO[None])
def run2() -> Do:
    channel = yield channel_id()
    yield variable_set('foo', value)
    v = yield variable_raw('foo')
    yield N.recover_failure(nvim_call_function('rpcrequest', channel, 'ping', sync=False), lambda a: N.pure('failed'))
    return v


@do(NvimIO[None])
def run1() -> Do:
    v = yield run2()
    yield nvim_command('quit')
    return v


responses: Map[str, Any] = Map(
    nvim_get_api_info=(1, {}),
)


@prog
@do(NS[None, None])
def ping() -> Do:
    yield NS.unit


config: Config = Config.cons('uv', rpc=List(rpc.write(ping)))


def embed_nvim(log: Path) -> Tuple[Asyncio, RpcComm]:
    embed_nvim_cmdline = List('nvim', f'-V{log}', '-n', '-u', 'NONE', '--embed')
    return cons_asyncio_embed(embed_nvim_cmdline)


@do(IO[A])
def run_nvim(comm: Comm, config: Config, io: Callable[[], NvimIO[A]]) -> Do:
    state = cons_state(config)
    guard = StateGuard.cons(state)
    execute_request = plugin_execute_receive_request(guard, 'spec')
    yield start_comm(comm, execute_request)
    api = RiboNvimApi(config.basic.name, comm)
    yield N.to_io_a(exclusive_ns(guard, 'init_rpc', init_rpc, Left('')), api)
    s, r = io().run(api)
    yield stop_comm(comm)
    return r


class NativeRpcSpec(SpecBase):
    '''
    native session $native
    external $external
    '''

    def native(self) -> Expectation:
        log = temp_file('log', 'uv')
        uv, rpc_comm = embed_nvim(log)
        comm = Comm.cons(rpc_handler, rpc_comm)
        return kio(run_nvim, comm, config, run1).must(contain(be_right(value)))

    @pending
    def external(self) -> Expectation:
        log = temp_file('log', 'uv')
        start_uv_embed_nvim_sync_log('uv', log)
        return k(1) == 1


__all__ = ('NativeRpcSpec',)
