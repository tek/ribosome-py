import sys
from asyncio import get_child_watcher, run_coroutine_threadsafe
from typing import Callable, Coroutine

from amino import IO, do, Do, Try
from amino.case import Case
from amino.logging import module_log

from ribosome.rpc.concurrency import OnMessage, OnError
from ribosome.rpc.io.data import (AsyncioResources, AsyncioPipes, Asyncio, AsyncioEmbed, EmbedProto, AsyncioStdio,
                                  BasicProto, AsyncioSocket)

log = module_log()


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
def asyncio_send(resources: AsyncioResources) -> Callable[[bytes], None]:
    def send(data: bytes) -> None:
        transport = resources.transport.result()
        Try(transport.write, data).lmap(lambda err: log.error(f'asyncio write failed: {err}'))
    return send


def join_asyncio_loop(asio: Asyncio) -> IO[None]:
    return asio.thread.thread.cata(lambda t: IO.delay(t.join), IO.failed(f'no asyncio loop running'))


def asyncio_exit(asio: Asyncio) -> None:
    pass


__all__ = ('asyncio_exit', 'join_asyncio_loop', 'asyncio_send', 'stop_processing', 'start_processing',)
