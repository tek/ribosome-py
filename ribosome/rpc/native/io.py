from asyncio import BaseEventLoop, SubprocessProtocol, get_child_watcher, WriteTransport
from threading import Thread
from typing import Callable, Tuple, Coroutine

from amino import Dat, List, IO, do, Do, ADT, Maybe, Nothing, Either
from amino.case import Case
from amino.logging import module_log

from ribosome.rpc.comm import RpcComm
from ribosome.rpc.concurrency import OnMessage, OnError

log = module_log()
Loop = BaseEventLoop


class EmbedProto(SubprocessProtocol):
    pass


class AsyncioPipes(ADT['AsyncioPipes']):
    pass


class AsyncioEmbed(AsyncioPipes):
    pass


class AsyncioLoopThread(Dat['AsyncioLoopThread']):

    def __init__(self, thread: Maybe[Thread]) -> None:
        self.thread = thread

    def update(self, thread: Thread) -> None:
        self.thread = Just(thread)

    def reset(self) -> None:
        self.thread = Nothing


class AsyncioResources:

    @staticmethod
    def cons(
            writer: WriteTransport=None,
    ) -> 'AsyncioResources':
        return AsyncioResources(
            Maybe.optional(writer),
        )

    def __init__(self, writer: Maybe[WriteTransport]) -> None:
        self.writer = writer

    def write(self, data: bytes) -> IO[None]:
        self.writer.cata(
            lambda w: IO.delay(w.write, data)
        )


class Asyncio(Dat['Asyncio']):

    @staticmethod
    def cons(
            loop: Loop,
            pipes: AsyncioPipes,
            thread: AsyncioLoopThread=None,
    ) -> 'Asyncio':
        return Asyncio(loop, pipes, thread or AsyncioLoopThread(Nothing))

    def __init__(self, loop: Loop, pipes: AsyncioPipes, thread: AsyncioLoopThread) -> None:
        self.loop = loop
        self.pipes = pipes
        self.thread = thread


def asyncio_embed(loop: Loop) -> None:
    pass


class connect_asyncio(Case[AsyncioPipes, IO[None]], alg=AsyncioPipes):

    def __init__(self, asio: Asyncio) -> None:
        self.asio = asio

    def embed(self, a: AsyncioEmbed) -> IO[Coroutine]:
        child_watcher = yield IO.delay(get_child_watcher)
        yield child_watcher.attach_loop(self.asio.loop)
        return self.asio.loop.subprocess_exec


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
        yield connect_asyncio(asio)(asio.pipes)
        thread = yield IO.fork(asyncio_main_loop, asio)
        yield IO.delay(asio.thread.update, thread)
    return start


def stop_processing(asio: Asyncio) -> Callable[[], IO[None]]:
    def stop() -> IO[None]:
        return stop_asyncio_loop(asio)
    return stop


# FIXME stop loop on error?
def asyncio_send(resources: AsyncioResources) -> Callable[[bytes], Either[str, None]]:
    def send(data: bytes) -> Either[str, None]:
        return Try(write.write, data).lmap(lambda err: log.error(f'asyncio write failed: {err}'))
    return send


def cons_asyncio(pipes: AsyncioPipes) -> Tuple[Asyncio, RpcComm]:
    loop = Loop()
    resources = AsyncioResources.cons()
    asio = Asyncio.cons(loop, resources, pipes)
    comm = RpcComm(start_processing(asio), stop_processing(asio), asyncio_send(resources),
                   asyncio_join(asio), asyncio_exit(loop))
    return asio, comm


def cons_asyncio_embed(proc: List[str]) -> Tuple[Asyncio, RpcComm]:
    return cons_asyncio(AsyncioEmbed())


__all__ = ('cons_asyncio_embed',)
