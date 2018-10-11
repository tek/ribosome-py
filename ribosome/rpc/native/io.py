import sys
from asyncio import (BaseEventLoop, SubprocessProtocol, get_child_watcher, WriteTransport, SelectorEventLoop,
                     SubprocessTransport, run_coroutine_threadsafe, new_event_loop, Protocol, Transport)
from threading import Thread
from typing import Callable, Tuple, Coroutine
from concurrent.futures import Future

from amino import Dat, List, IO, do, Do, ADT, Maybe, Nothing, Either, Just, Try, Path
from amino.case import Case
from amino.logging import module_log

from ribosome.rpc.comm import RpcComm
from ribosome.rpc.concurrency import OnMessage, OnError
from ribosome.rpc.error import processing_error, RpcReadErrorUnknown
from ribosome.config.config import Config
from ribosome.rpc.start import start_plugin_sync, cannot_execute_request, init_comm
from ribosome.rpc.nvim_api import RiboNvimApi

log = module_log()
Loop = BaseEventLoop


class EmbedProto(SubprocessProtocol):

    def __init__(self, asio: 'Asyncio', on_message: OnMessage, on_error: OnError) -> None:
        self.asio = asio
        self.on_message = on_message
        self.on_error = on_error

    def connection_made(self, transport: SubprocessTransport) -> None:
        self.asio.resources.transport.set_result(transport.get_pipe_transport(0))

    def pipe_connection_lost(self, fd: int, exc: Exception) -> None:
        log.error(f'lost: {fd}/{exc}')

    def pipe_data_received(self, fd: int, data: bytes) -> None:
        if fd == 1:
            self.on_message(data).attempt.leffect(processing_error(data))
        else:
            self.on_error(RpcReadErrorUnknown(data or b'no error message')).attempt.leffect(processing_error(None))

    def process_exited(self) -> None:
        pass


class BasicProto(Protocol):

    def __init__(self, asio: 'Asyncio', on_message: OnMessage, on_error: OnError) -> None:
        self.asio = asio
        self.on_message = on_message
        self.on_error = on_error

    def connection_made(self, transport: Transport) -> None:
        try:
            if isinstance(transport, WriteTransport):
                self.asio.resources.transport.set_result(transport)
        except Exception as e:
            log.caught_exception(f'setting transport {transport}', e)

    def connection_lost(self, exc: Exception) -> None:
        log.error(f'lost: {exc}')

    def data_received(self, data: bytes) -> None:
        self.on_message(data).attempt.leffect(processing_error(data))


class AsyncioPipes(ADT['AsyncioPipes']):
    pass


class AsyncioEmbed(AsyncioPipes):

    def __init__(self, proc: List[str]) -> None:
        self.proc = proc


class AsyncioStdio(AsyncioPipes):
    pass


class AsyncioSocket(AsyncioPipes):

    def __init__(self, path: Path) -> None:
        self.path = path


class AsyncioLoopThread(Dat['AsyncioLoopThread']):

    def __init__(self, thread: Maybe[Thread]) -> None:
        self.thread = thread

    def update(self, thread: Thread) -> None:
        self.thread = Just(thread)

    def reset(self) -> None:
        self.thread = Nothing


class AsyncioResources(Dat['AsyncioResources']):

    @staticmethod
    def cons(
            transport: Future,
    ) -> 'AsyncioResources':
        return AsyncioResources(
            transport,
        )

    def __init__(self, transport: Future) -> None:
        self.transport = transport


class Asyncio(Dat['Asyncio']):

    @staticmethod
    def cons(
            loop: Loop,
            pipes: AsyncioPipes,
            resources: AsyncioResources,
            thread: AsyncioLoopThread=None,
    ) -> 'Asyncio':
        return Asyncio(loop, pipes, resources, thread or AsyncioLoopThread(Nothing))

    def __init__(self, loop: Loop, pipes: AsyncioPipes, resources: AsyncioResources, thread: AsyncioLoopThread) -> None:
        self.loop = loop
        self.pipes = pipes
        self.resources = resources
        self.thread = thread


class connect_asyncio(Case[AsyncioPipes, IO[None]], alg=AsyncioPipes):

    def __init__(self, asio: Asyncio, on_message: OnMessage, on_error: OnError) -> None:
        self.asio = asio
        self.on_message = on_message
        self.on_error = on_error

    @do(IO[Coroutine])
    def embed(self, a: AsyncioEmbed) -> Do:
        child_watcher = yield IO.delay(get_child_watcher)
        yield IO.delay(child_watcher.attach_loop, self.asio.loop)
        return self.asio.loop.subprocess_exec(lambda: EmbedProto(self.asio, self.on_message, self.on_error), *a.proc)

    def stdio(self, pipes: AsyncioStdio) -> IO[Coroutine]:
        proto = BasicProto(self.asio, self.on_message, self.on_error)
        async def connect() -> None:
            await self.asio.loop.connect_read_pipe(lambda: proto, sys.stdin)
            await self.asio.loop.connect_write_pipe(lambda: proto, sys.stdout)
        return IO.pure(connect())

    def socket(self, pipes: AsyncioSocket) -> IO[Coroutine]:
        return self.asio.loop.create_unix_connection(
            lambda: BasicProto(self.asio, self.on_message, self.on_error),
            str(pipes.path),
        )


def asyncio_main_loop(asio: Asyncio) -> None:
    try:
        asio.loop.run_forever()
    except Exception as e:
        log.error(e)


@do(IO[None])
def stop_asyncio_loop(asio: Asyncio) -> Do:
    yield IO.delay(asio.loop.stop)
    yield asio.thread.thread.cata(lambda t: IO.delay(t.join, 3), IO.pure(None))
    yield IO.delay(asio.loop.close)
    yield IO.delay(asio.thread.reset)


def start_processing(asio: Asyncio) -> Callable[[OnMessage, OnError], IO[None]]:
    @do(IO[None])
    def start(on_message: OnMessage, on_error: OnError) -> Do:
        thread = yield IO.fork(asyncio_main_loop, asio)
        yield IO.delay(asio.thread.update, thread)
        connect = yield connect_asyncio(asio, on_message, on_error)(asio.pipes)
        conn_finished = yield IO.delay(run_coroutine_threadsafe, connect, asio.loop)
        yield IO.delay(conn_finished.result)
    return start


def stop_processing(asio: Asyncio) -> Callable[[], IO[None]]:
    def stop() -> IO[None]:
        return stop_asyncio_loop(asio)
    return stop


# FIXME stop loop on error?
def asyncio_send(resources: AsyncioResources) -> Callable[[bytes], Either[str, None]]:
    def send(data: bytes) -> Either[str, None]:
        transport = resources.transport.result()
        return Try(transport.write, data).lmap(lambda err: log.error(f'asyncio write failed: {err}'))
    return send


def join_asyncio_loop(asio: Asyncio) -> IO[None]:
    return asio.thread.thread.cata(lambda t: IO.delay(t.join), IO.failed(f'no asyncio loop running'))


def asyncio_exit(asio: Asyncio) -> None:
    pass


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


embed_nvim_cmdline = List('nvim', '-n', '-u', 'NONE', '--embed')


@do(IO[RiboNvimApi])
def start_asyncio_embed_nvim_sync(name: str, extra: List[str]) -> Do:
    asio, rpc_comm = cons_asyncio_embed(embed_nvim_cmdline + extra)
    comm = yield init_comm(rpc_comm, cannot_execute_request)
    return RiboNvimApi(name, comm)


def start_asyncio_embed_nvim_sync_log(name: str, log: Path) -> IO[RiboNvimApi]:
    return start_asyncio_embed_nvim_sync(name, List(f'-V{log}'))


__all__ = ('cons_asyncio_embed', 'cons_asyncio_stdio', 'cons_asyncio_socket', 'start_asyncio_plugin_sync',
           'start_asyncio_embed_nvim_sync', 'start_asyncio_embed_nvim_sync_log',)
