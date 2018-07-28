from typing import TypeVar, Any, Type, Callable

from amino import Try, Lists, Either, do, Do

from msgpack import ExtType
from amino.util.string import decode

from ribosome.nvim.io.compute import NvimIO, NvimIOPure, NvimIORequest
from ribosome.nvim.io.trace import NvimIOException
from ribosome.nvim.io.compute import NvimIOError
from ribosome.nvim.io.cons import nvimio_recover_fatal, nvimio_from_either

A = TypeVar('A')


def nvim_error_msg(exc: Exception) -> str:
    return Try(lambda: decode(exc.args[0])) | str(exc)


def nvim_request_error(name: str, args: tuple, desc: str, error: Any) -> NvimIO[A]:
    msg = (nvim_error_msg(error.cause) if isinstance(error, NvimIOException) else str(error))
    return NvimIOError(f'{desc} in nvim request `{name}({Lists.wrap(args).join_comma})`: {msg}')


@decode.register(ExtType)
def decode_ext_type(a: ExtType) -> ExtType:
    return a


@do(NvimIO[Either[str, A]])
def nvim_nonfatal_request(name: str, *args: Any, sync: bool=True) -> Do:
    request = NvimIORequest(name, Lists.wrap(args), sync)
    value = yield nvimio_recover_fatal(request, lambda a: nvim_request_error(name, args, 'fatal error', a))
    return value / decode


@do(NvimIO[A])
def nvim_request(name: str, *args: Any, sync: bool=True) -> Do:
    result = yield nvim_nonfatal_request(name, *args, sync=sync)
    yield nvimio_from_either(result)


def nvim_sync_request(name: str, *args: Any) -> NvimIO[A]:
    return nvim_request(name, *args, sync=True)


@do(NvimIO[A])
def typechecked_request(name: str, tpe: Type[A], *args: Any) -> Do:
    raw = yield nvim_sync_request(name, *args)
    yield (
        NvimIOPure(raw)
        if isinstance(raw, tpe) else
        NvimIOError(f'invalid result type of request {name}{args}: {raw}')
    )


@do(NvimIO[A])
def data_cons_request(name: str, cons: Callable[[Any], Either[str, A]], *args: Any) -> Do:
    raw = yield nvim_sync_request(name, *args)
    yield nvimio_from_either(cons(raw))


@do(NvimIO[Either[str, A]])
def data_cons_request_nonfatal(name: str, cons: Callable[[Either[str, Any]], Either[str, A]], *args: Any) -> Do:
    raw = yield nvim_nonfatal_request(name, *args, sync=True)
    return cons(raw)


__all__ = ('nvim_nonfatal_request', 'nvim_request', 'typechecked_request', 'data_cons_request',
           'data_cons_request_nonfatal')
