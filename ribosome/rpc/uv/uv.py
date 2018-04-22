import sys
import abc
from typing import Any, Callable, Optional, Tuple

import pyuv
from pyuv import (Pipe, Loop, Process, StdIO, UV_CREATE_PIPE, UV_READABLE_PIPE, UV_WRITABLE_PIPE,  # type: ignore
                  UV_PROCESS_WINDOWS_HIDE)

from amino import Dat, Try, Either, ADT, IO, List, do, Do, Maybe, Just, Nothing
from amino.logging import module_log
from amino.case import Case

from ribosome.rpc.comm import RpcComm, OnMessage, OnError
from ribosome.rpc.error import RpcReadErrorUnknown, RpcProcessExit

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


class Uv(Dat['Uv']):

    def __init__(
            self,
            loop: Loop,
            resources: UvResources,
    ) -> None:
        self.loop = loop
        self.resources = resources


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


def embed(loop: Loop, proc: List[str]) -> UvResources:
    write = Pipe(loop)
    read = Pipe(loop)
    error = Pipe(loop)
    stdin = StdIO(write, flags=UV_CREATE_PIPE + UV_READABLE_PIPE)
    stdout = StdIO(read, flags=UV_CREATE_PIPE + UV_WRITABLE_PIPE)
    stderr = StdIO(error, flags=UV_CREATE_PIPE + UV_WRITABLE_PIPE)
    return UvEmbedResources(write, read, error, stdin, stdout, stderr, proc)


def on_async(*a: Any) -> None:
    print(f'async: {a}')


def on_exit(handle: Pipe, exit_status: int, term_signal: int) -> None:
    print(f'exit: {exit_status}')


OnRead = Callable[[Pipe, Optional[bytes], Optional[int]], None]


def processing_error(error: Exception) -> None:
    log.error(f'error processing message from nvim: {error}')


def read_pipe(on_data: OnMessage, on_error: OnError) -> OnRead:
    def read(handle: Pipe, data: Optional[bytes], error: Optional[int]) -> None:
        '''error -4095 is EOF, regular message when quitting
        '''
        if data is not None:
            on_data(data).attempt.leffect(processing_error)
        if error is not None:
            message = pyuv.errno.strerror(error)
            info = RpcProcessExit() if error == -4095 else RpcReadErrorUnknown(message)
            on_error(info).attempt.leffect(processing_error)
    return read


def start_processing(uv: Uv) -> Callable[[OnMessage, OnError], IO[None]]:
    @do(IO[None])
    def start(on_message: OnMessage, on_error: OnError) -> Do:
        on_read = read_pipe(on_message, on_error)
        yield connect_uv(uv, on_read)(uv.resources)
        yield IO.delay(uv.resources.read_source.start_read, on_read)
    return start


def uv(cons_resources: Callable[[Loop], UvResources]) -> Tuple[Uv, RpcComm]:
    loop = Loop()
    resources = cons_resources(loop)
    uv = Uv(loop, resources)
    comm = RpcComm(start_processing(uv), uv_send(resources.write_sink), uv_exit(loop))
    return uv, comm


def cons_uv_embed(proc: List[str]) -> Tuple[Uv, RpcComm]:
    return uv(lambda loop: embed(loop, proc))


class UvConnection(ADT['UvConnection']):
    pass


class UvEmbedConnection(UvConnection):

    def __init__(self, proc: Process) -> None:
        self.proc = proc


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


class ConnectedUv(Dat['ConnectedUv']):

    def __init__(self, uv: Uv, connection: UvConnection) -> None:
        self.uv = uv
        self.connection = connection


__all__ = ()
