from typing import Tuple, Any

from amino import _, Either, Map, Left, Right, do, Do
from amino.state import State

from ribosome.nvim.io.compute import NvimIO, NvimIOSuspend, NvimIOPure
from ribosome.nvim.io.api import N
from ribosome.nvim.api.function import nvim_call_function, nvim_call_tpe
from ribosome.nvim.api.command import nvim_command
from ribosome import NvimApi


def plugin_name() -> NvimIO[str]:
    return N.delay(_.name)


def api_info() -> NvimIO[Tuple[int, dict]]:
    def cons(data: Any) -> Either[str, Tuple[int, Map[str, Any]]]:
        return (
            Left(f'not a tuple: {data}')
            if not isinstance(data, (list, tuple)) else
            Left(f'invalid tuple size: {data}')
            if not len(data) == 2 else
            Left(f'channel is not an int: {data}')
            if not isinstance(data[0], int) else
            Left(f'metadata is not a dict: {data}')
            if not isinstance(data[1], dict) else
            Right(data).map2(lambda a, b: (a, Map(b)))
        )
    return N.read_cons('nvim_get_api_info', cons)


@do(NvimIO[int])
def channel_id() -> Do:
    channel, metadata = yield api_info()
    return channel


def rpcrequest(channel: int, method: str, *args: str) -> NvimIO[Any]:
    return nvim_call_function('rpcrequest', channel, method, args)


@do(NvimIO[Any])
def rpcrequest_current(method: str, *args: str) -> Do:
    channel = yield channel_id()
    yield rpcrequest(channel, method, *args)


def nvim_quit() -> NvimIO[None]:
    return nvim_command('qall!')


def nvim_api() -> NvimIO[NvimApi]:
    return NvimIOSuspend.cons(State.get().map(NvimIOPure))


def nvim_pid() -> NvimIO[int]:
    return nvim_call_tpe(int, 'getpid')


__all__ = ('plugin_name', 'api_info', 'channel_id', 'rpcrequest', 'rpcrequest_current', 'nvim_quit', 'nvim_api',
           'nvim_pid',)
