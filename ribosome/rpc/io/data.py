from asyncio import BaseEventLoop, WriteTransport, SubprocessTransport, Transport
from threading import Thread
from concurrent.futures import Future

from amino import Dat, List, ADT, Maybe, Nothing, Just, Path
from amino.logging import module_log

from ribosome.rpc.concurrency import OnMessage, OnError
from ribosome.rpc.error import processing_error, RpcReadErrorUnknown

log = module_log()


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
            loop: BaseEventLoop,
            pipes: AsyncioPipes,
            resources: AsyncioResources,
            thread: AsyncioLoopThread=None,
    ) -> 'Asyncio':
        return Asyncio(loop, pipes, resources, thread or AsyncioLoopThread(Nothing))

    def __init__(
            self,
            loop: BaseEventLoop,
            pipes: AsyncioPipes,
            resources: AsyncioResources,
            thread: AsyncioLoopThread,
    ) -> None:
        self.loop = loop
        self.pipes = pipes
        self.resources = resources
        self.thread = thread


class EmbedProto(Dat['EmbedProto']):

    def __init__(self, asio: Asyncio, on_message: OnMessage, on_error: OnError) -> None:
        self.asio = asio
        self.on_message = on_message
        self.on_error = on_error

    def connection_made(self, transport: SubprocessTransport) -> None:
        self.asio.resources.transport.set_result(transport.get_pipe_transport(0))

    def connection_lost(self, exc: Exception) -> None:
        log.error(f'lost: {exc}')

    def pipe_connection_lost(self, fd: int, exc: Exception) -> None:
        log.error(f'lost: {fd}/{exc}')

    def pipe_data_received(self, fd: int, data: bytes) -> None:
        if fd == 1:
            self.on_message(data).attempt.leffect(processing_error(data))
        else:
            self.on_error(RpcReadErrorUnknown(data or b'no error message')).attempt.leffect(processing_error(None))

    def process_exited(self) -> None:
        pass


class BasicProto(Dat['BasicProto']):

    def __init__(self, asio: Asyncio, on_message: OnMessage, on_error: OnError) -> None:
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


__all__ = ('EmbedProto', 'BasicProto', 'AsyncioPipes', 'AsyncioEmbed', 'AsyncioStdio', 'AsyncioSocket',
           'AsyncioLoopThread', 'AsyncioResources', 'Asyncio',)
