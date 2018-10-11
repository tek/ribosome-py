from asyncio import new_event_loop
from typing import Tuple
from concurrent.futures import Future

from amino import List, IO, do, Do, Path
from amino.logging import module_log

from ribosome.rpc.comm import RpcComm
from ribosome.config.config import Config
from ribosome.rpc.start import start_plugin_sync, cannot_execute_request, init_comm
from ribosome.rpc.nvim_api import RiboNvimApi
from ribosome.rpc.io.data import AsyncioPipes, Asyncio, AsyncioResources, AsyncioEmbed, AsyncioStdio, AsyncioSocket
from ribosome.rpc.io.connect import start_processing, stop_processing, asyncio_send, join_asyncio_loop, asyncio_exit

log = module_log()
embed_nvim_cmdline = List('nvim', '-n', '-u', 'NONE', '--embed')


def cons_asyncio(pipes: AsyncioPipes) -> Tuple[Asyncio, RpcComm]:
    loop = new_event_loop()
    resources = AsyncioResources.cons(Future())
    asio = Asyncio.cons(loop, pipes, resources)
    comm = RpcComm(
        start_processing(asio),
        stop_processing(asio),
        asyncio_send(resources),
        lambda: join_asyncio_loop(asio),
        lambda: asyncio_exit(asio),
    )
    return asio, comm


def cons_asyncio_embed(proc: List[str]) -> Tuple[Asyncio, RpcComm]:
    return cons_asyncio(AsyncioEmbed(proc))


def cons_asyncio_stdio() -> Tuple[Asyncio, RpcComm]:
    return cons_asyncio(AsyncioStdio())


def cons_asyncio_socket(path: Path) -> Tuple[Asyncio, RpcComm]:
    return cons_asyncio(AsyncioSocket(path))


def start_asyncio_plugin_sync(config: Config) -> IO[None]:
    asio, rpc_comm = cons_asyncio_stdio()
    return start_plugin_sync(config, rpc_comm)


@do(IO[RiboNvimApi])
def start_asyncio_embed_nvim_sync(name: str, extra: List[str]) -> Do:
    asio, rpc_comm = cons_asyncio_embed(embed_nvim_cmdline + extra)
    comm = yield init_comm(rpc_comm, cannot_execute_request)
    return RiboNvimApi(name, comm)


def start_asyncio_embed_nvim_sync_log(name: str, log: Path) -> IO[RiboNvimApi]:
    return start_asyncio_embed_nvim_sync(name, List(f'-V{log}'))


__all__ = ('cons_asyncio_embed', 'cons_asyncio_stdio', 'cons_asyncio_socket', 'start_asyncio_plugin_sync',
           'start_asyncio_embed_nvim_sync', 'start_asyncio_embed_nvim_sync_log',)
