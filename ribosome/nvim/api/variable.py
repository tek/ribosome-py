from numbers import Number
from typing import Any, Callable, TypeVar

from amino import Either, do, Do, Left, I
from amino.logging import module_log

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.rpc import plugin_name
from ribosome.nvim.api.util import cons_decode_str, cons_checked_e
from ribosome.nvim.api.data import Buffer
from ribosome.nvim.request import nvim_nonfatal_request, data_cons_request_nonfatal, nvim_request
from ribosome.nvim.io.api import N

log = module_log()
A = TypeVar('A')


def variable_raw(name: str) -> NvimIO[Either[str, Any]]:
    return nvim_nonfatal_request('nvim_get_var', name)


@do(NvimIO[Either[str, Any]])
def variable_prefixed_raw(name: str) -> Do:
    plug = yield plugin_name()
    yield variable_raw(f'{plug}_{name}')


@do(NvimIO[Either[str, A]])
def variable(name: str, cons: Callable[[Any], Either[str, A]]) -> Do:
    log.debug(f'request variable `{name}`')
    def cons_e(result: Either[str, Any]) -> Either[str, A]:
        return result.cata(lambda err: Left(f'variable unset: {name}'), cons)
    value = yield data_cons_request_nonfatal('nvim_get_var', cons_e, name)
    log.debug(f'variable `{name}`: {value}')
    return value


def variable_str(name: str) -> NvimIO[Either[str, str]]:
    return variable(name, cons_decode_str)


def variable_num(name: str) -> NvimIO[Either[str, Number]]:
    return variable(name, cons_checked_e(Number, I))


@do(NvimIO[Either[str, A]])
def variable_prefixed(name: str, cons: Callable[[Any], Either[str, A]]) -> Do:
    plug = yield plugin_name()
    yield variable(f'{plug}_{name}', cons)


def variable_prefixed_str(name: str) -> NvimIO[Either[str, str]]:
    return variable_prefixed(name, cons_decode_str)


def variable_prefixed_num(name: str) -> NvimIO[Either[str, Number]]:
    return variable_prefixed(name, cons_checked_e(Number, I))


def variable_set(name: str, value: Any) -> NvimIO[None]:
    return N.write('nvim_set_var', name, value)


@do(NvimIO[None])
def variable_set_prefixed(name: str, value: Any) -> Do:
    plug = yield plugin_name()
    yield N.write('nvim_set_var', f'{plug}_{name}', value)


def buffer_var_raw(buffer: Buffer, name: str) -> NvimIO[Any]:
    return nvim_request('nvim_buf_get_var', buffer.data, name)


__all__ = ('variable_raw', 'variable_prefixed_raw', 'variable', 'variable_prefixed', 'variable_prefixed_str',
           'variable_prefixed_num', 'variable_set', 'variable_set_prefixed', 'buffer_var_raw', 'variable_str',
           'variable_num')
