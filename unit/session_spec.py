import time
from typing import Any, Tuple, Callable
from threading import Thread, Lock
from queue import Queue
from concurrent.futures import Future

from pyuv import (Pipe, Loop, Async, Process, StdIO, UV_CREATE_PIPE, UV_READABLE_PIPE, UV_WRITABLE_PIPE,  # type: ignore
                  UV_PROCESS_WINDOWS_HIDE)

import msgpack

from kallikrein import k, Expectation
from kallikrein.matchers import contain
from kallikrein.matchers.either import be_right

from amino import Dat, List, Try, _, do, Do, Either, ADT, Left, Map, Right, Lists
from amino.test import temp_file
from amino.test.spec import SpecBase
from amino.state import EitherState
from amino.logging import module_log
from amino.case import Case

from ribosome import NvimApi
from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.variable import variable_set, variable_raw
from ribosome.nvim.api.command import nvim_command
from ribosome.nvim.io.data import NSuccess

log = module_log()


class Receive(ADT['Receive']):
    pass


class Response(Receive):

    def __init__(self, id: int, data: Any) -> None:
        self.id = id
        self.data = data


class Error(Receive):

    def __init__(self, id: int, error: str) -> None:
        self.id = id
        self.error = error


class Exit(Receive):
    pass


class Unknown(Receive):

    def __init__(self, data: Any, reason: str) -> None:
        self.data = data
        self.reason = reason


@do(Either[str, Receive])
def receive_error(id: int, el3: Any) -> Do:
    yield Right(el3) if isinstance(el3, list) else Left(f'error payload not a list: {el3}')
    error = yield Lists.wrap(el3).lift(1).to_either_f(lambda: f'too few elements for error payload: {el3}')
    return Error(id, error)


@do(Either[str, Receive])
def validate_receive_data(data: Any) -> Do:
    yield Right(None) if isinstance(data, list) else Left('not a list')
    l = len(data)
    el2, el3, el4 = yield Lists.wrap(data).lift_all(1, 2, 3).to_either_f(lambda: f'wrong number of elements: {l}')
    id = yield Right(el2) if isinstance(el2, int) else Left(f'id is not an int: {el2}')
    yield (
        receive_error(id, el3)
        if el3 is not None else
        Right(Response(id, el4))
    )


def cons_receive(data: Any) -> Receive:
    return validate_receive_data(data).value_or(lambda reason: Unknown(data, reason))


class Requests(Dat['Requests']):

    def __init__(self, current_id: int, pending: Map[int, Future]) -> None:
        self.current_id = current_id
        self.pending = pending


class Uv(Dat['Uv']):

    def __init__(
            self,
            loop: Loop,
            asyn: Async,
            write: Pipe,
            read: Pipe,
            error: Pipe,
            proc: Process,
            comm: Queue,
            requests: Requests,
            lock: Lock,
    ) -> None:
        self.loop = loop
        self.asyn = asyn
        self.write = write
        self.read = read
        self.error = error
        self.proc = proc
        self.comm = comm
        self.requests = requests
        self.lock = lock


def on_error(pipe: Pipe, blob: bytes, error: int) -> None:
    print(f'error: {blob} {error}')


def read_error(reason: str) -> None:
    log.error(f'error reading from nvim: {reason}')


def on_read_handler(requests: Requests, lock: Lock) -> Callable[[Pipe, bytes, int], None]:
    @do(Either[str, None])
    def on_read(pipe: Pipe, blob: bytes, error: int) -> Do:
        data = yield Try(msgpack.unpackb, blob).lmap(lambda e: f'failed to unpack: {e}')
        receive = cons_receive(data)
        yield handle_receive(lock, requests)(receive)
    def handler(pipe: Pipe, blob: bytes, error: int) -> None:
        result = on_read(pipe, blob, error)
        result.leffect(read_error)
    return handler


def child(argv: list) -> Uv:
    comm = Queue()
    requests = Requests(0, Map())
    lock = Lock()
    def on_async(*a: Any) -> None:
        print(f'async: {a}')
    def on_exit(handle: Pipe, exit_status: int, term_signal: int) -> None:
        print(f'exit: {exit_status}')
        Try(comm.put, Exit())
    loop = Loop()
    asyn = Async(loop, on_async)
    write_stream = Pipe(loop)
    read_stream = Pipe(loop)
    error_stream = Pipe(loop)
    stdin = StdIO(write_stream, flags=UV_CREATE_PIPE + UV_READABLE_PIPE)
    stdout = StdIO(read_stream, flags=UV_CREATE_PIPE + UV_WRITABLE_PIPE)
    stderr = StdIO(error_stream, flags=UV_CREATE_PIPE + UV_WRITABLE_PIPE)
    proc = Process.spawn(
        loop,
        args=argv,
        exit_callback=on_exit,
        flags=UV_PROCESS_WINDOWS_HIDE,
        stdio=(stdin, stdout, stderr,),
    )
    error_stream.start_read(on_error)
    read_stream.start_read(on_read_handler(requests, lock))
    return Uv(loop, asyn, write_stream, read_stream, error_stream, proc, comm, requests, lock)


class Rpc(Dat['Rpc']):

    def __init__(self, method: str, args: List[Any]) -> None:
        self.method = method
        self.args = args


request_timeout = 1.


class UvNvimApi(NvimApi):

    def __init__(self, name: str, uv: Uv) -> None:
        self.name = name
        self.uv = uv

    @do(Either[str, Tuple[NvimApi, Any]])
    def request(self, method: str, args: List[Any], sync: bool) -> Do:
        sender = send_request if sync else send_notification
        rpc_desc = 'request' if sync else 'notification'
        try:
            log.debug(f'api: {rpc_desc} `{method}`')
            uv, result = yield sender(Rpc(method, args), request_timeout).run(self.uv)
            return self.copy(uv=uv), result
        except Exception as e:
            yield Left(f'request error: {e}')


def exclusive_increment(uv: Uv) -> Uv:
    with uv.lock:
        uv.requests.current_id += 1
    return uv


def exclusive_register_callback(uv: Uv, id: int, rpc: Rpc) -> Future:
    result = Future()
    with uv.lock:
        uv.requests.pending[id] = (result, rpc)
    return result


def resolve_rpc(requests: Requests, id: int) -> Either[Exception, Tuple[Future, Rpc]]:
    return Try(requests.pending.pop, id)


@do(Either[str, None])
def notify(requests: Map[int, Future], data: Response) -> do:
    print(f'notify: {data}')
    fut, rpc = yield resolve_rpc(requests, data.id)
    yield Try(fut.set_result, data.data)


@do(Either[str, None])
def notify_error(requests: Map[int, Future], err: Error) -> do:
    print(f'notify_error: {err}')
    fut, rpc = yield resolve_rpc(requests, err.id)
    yield Try(fut.cancel)
    yield Left(f'{rpc} failed: {err.error}')


class handle_receive(Case[Receive, Either[str, None]], alg=Receive):

    def __init__(self, lock: Lock, requests: Map[id, Future]) -> None:
        self.lock = lock
        self.requests = requests

    def response(self, data: Response) -> Either[str, None]:
        with self.lock:
            return notify(self.requests, data)

    def error(self, err: Error) -> Either[str, None]:
        with self.lock:
            return notify_error(self.requests, err)

    def case_default(self, data: Receive) -> Either[str, None]:
        return Try(log.error, f'unhandled Receive: {data}')


@do(EitherState[Uv, int])
def increment() -> Do:
    yield EitherState.modify(exclusive_increment)
    yield EitherState.inspect(_.requests.current_id)


@do(EitherState[Uv, Any])
def send_rpc(metadata: list, rpc: Rpc) -> Do:
    def write_error(handle: Pipe, error: Any) -> None:
        print(f'write error: {error}')
    write = yield EitherState.inspect(lambda a: a.write)
    yield EitherState.lift(Try(write.write, msgpack.packb(metadata + [rpc.method.encode(), rpc.args]), write_error))


@do(EitherState[Uv, Any])
def send_request(rpc: Rpc, timeout: float) -> Do:
    id = yield increment()
    result = yield EitherState.inspect(lambda a: exclusive_register_callback(a, id, rpc))
    yield send_rpc([0, id], rpc)
    r = yield EitherState.lift(Try(result.result, timeout).lmap(lambda a: f'{rpc} timed out after {timeout}s'))
    print(f'send_request result: {r}')


@do(EitherState[Uv, Any])
def send_notification(rpc: Rpc, timeout: float) -> Do:
    yield send_rpc([2], rpc)


def stop(p: Uv) -> None:
    p.loop.stop()


def main_loop(uv: Uv) -> None:
    Try(uv.loop.run).leffect(log.error)


value = 'successfully set variable'


@do(NvimIO[None])
def run1() -> Do:
    yield variable_set('foo', value)
    v = yield variable_raw('foo')
    yield nvim_command('quit', sync=False)
    return v


class SessionSpec(SpecBase):
    '''
    test $test
    '''

    def test(self) -> Expectation:
        log = temp_file('log', 'uv')
        cmdline = List('nvim', f'-V{log}', '-n', '-u', 'NONE', '--embed')
        uv = child(cmdline)
        main = Thread(target=main_loop, args=(uv,))
        main.start()
        self._wait(.5)
        api = UvNvimApi('uv', uv)
        s, r = run1().run(api)
        if not isinstance(r, NSuccess):
            print(r)
        # send_notification(Rpc('nvim_command', List('quit')), 1).run(uv)
        stop(uv)
        main.join()
        return k(r).must(contain(be_right(value)))


__all__ = ('SessionSpec',)
