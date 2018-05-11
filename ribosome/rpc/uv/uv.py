import sys
import abc
from typing import Callable, Optional, Tuple, Any
from threading import Thread
from concurrent.futures import Future

import pyuv
from pyuv import (Pipe, Loop, Process, StdIO, UV_CREATE_PIPE, UV_READABLE_PIPE, UV_WRITABLE_PIPE,  # type: ignore
                  UV_PROCESS_WINDOWS_HIDE, TCP)

from amino import Dat, Try, Either, ADT, IO, List, do, Do, Maybe, Just, Nothing, Path
from amino.logging import module_log
from amino.case import Case

from ribosome.rpc.comm import RpcComm, OnMessage, OnError
from ribosome.rpc.error import RpcReadErrorUnknown, RpcProcessExit
from ribosome.rpc.start import start_plugin_sync, init_comm, cannot_execute_request
from ribosome.config.config import Config
from ribosome.rpc.nvim_api import RiboNvimApi

log = module_log()


class UvResources(ADT['UvResources']):

    @abc.abstractproperty
    def write_sink(self) -> Pipe:
        ...

    @abc.abstractproperty
    def read_source(self) -> Pipe:
        ...

    @abc.abstractproperty
    def error_source(self) -> Maybe[Pipe]:
        ...


class UvStdioResources(UvResources):

    def __init__(
            self,
            write: Pipe,
            read: Pipe,
    ) -> None:
        self.write = write
        self.read = read

    @property
    def write_sink(self) -> Pipe:
        return self.write

    @property
    def read_source(self) -> Pipe:
        return self.read

    @property
    def error_source(self) -> Maybe[Pipe]:
        return Nothing


class UvEmbedResources(UvResources):

    def __init__(
            self,
            write: Pipe,
            read: Pipe,
            error: Pipe,
            stdin: StdIO,
            stdout: StdIO,
            stderr: StdIO,
            proc: List[str],
    ) -> None:
        self.write = write
        self.read = read
        self.error = error
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.proc = proc

    @property
    def write_sink(self) -> Pipe:
        return self.write

    @property
    def read_source(self) -> Pipe:
        return self.read

    @property
    def error_source(self) -> Maybe[Pipe]:
        return Just(self.write)


class UvTcpResources(UvResources):

    def __init__(
            self,
            tcp: TCP,
            address: str,
            port: int,
    ) -> None:
        self.tcp = tcp
        self.address = address
        self.port = port

    @property
    def write_sink(self) -> Pipe:
        return self.tcp

    @property
    def read_source(self) -> Pipe:
        return self.tcp

    @property
    def error_source(self) -> Maybe[Pipe]:
        return Nothing


class UvSocketResources(UvResources):

    def __init__(
            self,
            pipe: Pipe,
            socket: Path,
    ) -> None:
        self.pipe = pipe
        self.socket = socket

    @property
    def write_sink(self) -> Pipe:
        return self.pipe

    @property
    def read_source(self) -> Pipe:
        return self.pipe

    @property
    def error_source(self) -> Maybe[Pipe]:
        return Nothing


class UvLoopThread(Dat['UvLoopThread']):

    def __init__(self, thread: Maybe[Thread]) -> None:
        self.thread = thread

    def update(self, thread: Thread) -> None:
        self.thread = Just(thread)

    def reset(self) -> None:
        self.thread = Nothing


class Uv(Dat['Uv']):

    @staticmethod
    def cons(
            loop: Loop,
            resources: UvResources,
            thread: UvLoopThread=None,
    ) -> 'Uv':
        return Uv(loop, resources, thread or UvLoopThread(Nothing))

    def __init__(
            self,
            loop: Loop,
            resources: UvResources,
            thread: UvLoopThread,
    ) -> None:
        self.loop = loop
        self.resources = resources
        self.thread = thread


# TODO this must stop the loop
def uv_write_error(handle: Pipe, error: Optional[int]) -> None:
    if error is not None:
        log.debug(f'uv write error: {pyuv.errno.strerror(error)}')


def uv_send(write: Pipe) -> Callable[[bytes], Either[str, None]]:
    def send(data: bytes) -> Either[str, None]:
        return Try(write.write, data, uv_write_error).lmap(lambda err: log.error(f'uv write failed: {err}'))
    return send


def uv_exit(loop: Loop) -> Callable[[], None]:
    def exit() -> None:
        Try(loop.stop).leffect(log.error)
    return exit


def uv_stdio(loop: Loop) -> UvResources:
    write = Pipe(loop)
    read = Pipe(loop)
    return UvStdioResources(write, read)


def uv_embed(loop: Loop, proc: List[str]) -> UvResources:
    write = Pipe(loop)
    read = Pipe(loop)
    error = Pipe(loop)
    stdin = StdIO(write, flags=UV_CREATE_PIPE + UV_READABLE_PIPE)
    stdout = StdIO(read, flags=UV_CREATE_PIPE + UV_WRITABLE_PIPE)
    stderr = StdIO(error, flags=UV_CREATE_PIPE + UV_WRITABLE_PIPE)
    return UvEmbedResources(write, read, error, stdin, stdout, stderr, proc)


def uv_tcp(loop: Loop, address: str, port: int) -> UvResources:
    return UvTcpResources(TCP(loop), address)


def uv_socket(loop: Loop, socket: Path) -> UvResources:
    return UvSocketResources(Pipe(loop), socket)


def on_exit(handle: Pipe, exit_status: int, term_signal: int) -> None:
    if exit_status != 0:
        log.warn(f'uv loop exited with status {exit_status}, signal {term_signal}')


OnRead = Callable[[Pipe, Optional[bytes], Optional[int]], None]


def processing_error(data: Optional[bytes]) -> Callable[[Exception], None]:
    def processing_error(error: Exception) -> None:
        if data:
            log.debug(f'{error}: {data}')
        log.error(f'error processing message from nvim: {error}')
    return processing_error


def read_pipe(on_data: OnMessage, on_error: OnError) -> OnRead:
    def read(handle: Pipe, data: Optional[bytes], error: Optional[int]) -> None:
        '''error -4095 is EOF, regular message when quitting
        '''
        if data is not None:
            on_data(data).attempt.leffect(processing_error(data))
        if error is not None:
            message = pyuv.errno.strerror(error)
            info = RpcProcessExit() if error == -4095 else RpcReadErrorUnknown(message)
            on_error(info).attempt.leffect(processing_error(None))
    return read


def uv_main_loop(uv: Uv) -> None:
    try:
        uv.loop.run()
    except Exception as e:
        log.error(e)


def start_processing(uv: Uv) -> Callable[[OnMessage, OnError], IO[None]]:
    @do(IO[None])
    def start(on_message: OnMessage, on_error: OnError) -> Do:
        on_read = read_pipe(on_message, on_error)
        yield connect_uv(uv, on_read)(uv.resources)
        yield IO.delay(uv.resources.read_source.start_read, on_read)
        thread = yield IO.fork(uv_main_loop, uv)
        yield IO.delay(uv.thread.update, thread)
    return start


@do(IO[None])
def stop_uv_loop(uv: Uv) -> Do:
    yield IO.delay(uv.loop.stop)
    yield uv.thread.thread.cata(lambda t: IO.delay(t.join, 3), IO.pure(None))
    yield IO.delay(uv.thread.reset)


def stop_processing(uv: Uv) -> Callable[[], IO[None]]:
    def stop() -> IO[None]:
        return stop_uv_loop(uv)
    return stop


def join_uv_loop(uv: Uv) -> IO[None]:
    return uv.thread.thread.cata(lambda t: IO.delay(t.join), IO.failed(f'no uv loop running'))


def uv_join(uv: Uv) -> Callable[[], IO[None]]:
    def join() -> IO[None]:
        return join_uv_loop(uv)
    return join


def cons_uv(cons_resources: Callable[[Loop], UvResources]) -> Tuple[Uv, RpcComm]:
    loop = Loop()
    resources = cons_resources(loop)
    uv = Uv.cons(loop, resources)
    comm = RpcComm(start_processing(uv), stop_processing(uv), uv_send(resources.write_sink), uv_join(uv),
                   uv_exit(loop))
    return uv, comm


def cons_uv_embed(proc: List[str]) -> Tuple[Uv, RpcComm]:
    return cons_uv(lambda loop: uv_embed(loop, proc))


def cons_uv_stdio() -> Tuple[Uv, RpcComm]:
    return cons_uv(lambda loop: uv_stdio(loop))


def cons_uv_tcp(address: str) -> Tuple[Uv, RpcComm]:
    return cons_uv(lambda loop: uv_tcp(loop, address))


def cons_uv_socket(socket: Path) -> Tuple[Uv, RpcComm]:
    return cons_uv(lambda loop: uv_socket(loop, socket))


class UvConnection(ADT['UvConnection']):
    pass


class UvEmbedConnection(UvConnection):

    def __init__(self, proc: Process) -> None:
        self.proc = proc


def nvim_connected(handle: Pipe, error: Any) -> None:
    if error:
        log.error(f'connecting to nvim: {error}')


class connect_uv(Case[UvResources, IO[UvConnection]], alg=UvResources):

    def __init__(self, uv: Uv, on_read: Callable[[Pipe, bytes, int], None]) -> None:
        self.uv = uv
        self.on_read = on_read

    @do(IO[UvConnection])
    def stdio(self, resources: UvStdioResources) -> Do:
        yield IO.delay(resources.read.open, sys.stdin.fileno())
        yield IO.delay(resources.write.open, sys.stdout.fileno())

    @do(IO[UvConnection])
    def embed(self, resources: UvEmbedResources) -> Do:
        proc = yield IO.delay(
            Process.spawn,
            self.uv.loop,
            args=resources.proc,
            exit_callback=on_exit,
            flags=UV_PROCESS_WINDOWS_HIDE,
            stdio=(resources.stdin, resources.stdout, resources.stderr),
        )
        yield IO.delay(resources.error.start_read, self.on_read)
        return UvEmbedConnection(proc)

    @do(IO[UvConnection])
    def tcp(self, resources: UvTcpResources) -> Do:
        yield IO.delay(resources.tcp.connect, (resources.address, resources.port), nvim_connected)
        yield IO.delay(resources.tcp.start_read, self.on_read)

    @do(IO[UvConnection])
    def socket(self, resources: UvSocketResources) -> Do:
        yield IO.delay(resources.pipe.connect, str(resources.socket), nvim_connected)
        yield IO.delay(resources.pipe.start_read, self.on_read)


class ConnectedUv(Dat['ConnectedUv']):

    def __init__(self, uv: Uv, connection: UvConnection) -> None:
        self.uv = uv
        self.connection = connection


def start_uv_plugin_sync(config: Config) -> IO[None]:
    uv, rpc_comm = cons_uv_stdio()
    return start_plugin_sync(config, rpc_comm)


embed_nvim_cmdline = List('nvim', '-n', '-u', 'NONE', '--embed')


@do(IO[RiboNvimApi])
def start_uv_embed_nvim_sync(name: str, extra: List[str]) -> Do:
    uv, rpc_comm = cons_uv(lambda loop: uv_embed(loop, embed_nvim_cmdline + extra))
    comm = yield init_comm(rpc_comm, cannot_execute_request)
    return RiboNvimApi(name, comm)


def start_uv_embed_nvim_sync_log(name: str, log: Path) -> IO[RiboNvimApi]:
    return start_uv_embed_nvim_sync(name, List(f'-V{log}'))


__all__ = ()
