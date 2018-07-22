from __future__ import annotations
import abc
from typing import Any, Callable, Tuple

from msgpack import ExtType

from amino import List, Either, Map, Left, Dat, Nil, do, Do
from amino.logging import module_log

log = module_log()


class NvimApi(Dat['NvimApi']):

    def __init__(self, name: str) -> None:
        self.name = name

    @abc.abstractmethod
    def request(self, method: str, args: List[Any], sync: bool) -> Either[str, Tuple['NvimApi', Any]]:
        ...


StrictNvimHandler = Callable[['StrictNvimApi', str, List[Any], bool], Either[List[str], Tuple[NvimApi, Any]]]


def no_request_handler(vim: 'StrictNvimApi', method: str, args: List[Any], sync: bool
                       ) -> Either[List[str], Tuple[NvimApi, Any]]:
    return Left(List('no request handler defined'))


class StrictNvimApi(NvimApi):

    @staticmethod
    def cons(
            name: str,
            vars: Map[str, Any]=Map(),
            request_handler: StrictNvimHandler=no_request_handler,
            request_log: List[Tuple[str, List[Any]]]=Nil,
    ) -> 'StrictNvimApi':
        return StrictNvimApi(name, vars, request_handler, request_log)

    def __init__(
            self,
            name: str,
            vars: Map[str, Any],
            request_handler: StrictNvimHandler,
            request_log: List[Tuple[str, List[Any]]],
    ) -> None:
        self.name = name
        self.vars = vars
        self.request_handler = request_handler
        self.request_log = request_log

    def request(self, method: str, args: List[Any], sync: bool) -> Either[str, Tuple[NvimApi, Any]]:
        vim = self.append1.request_log((method, args))
        return self.request_handler(vim, method, args, sync).accum_error_lift(variable_request, vim, method, args)

    def var(self, name: str) -> Either[str, Any]:
        return self.vars.lift(name).to_either(f'no variable `{name}` defined')


@do(Either[str, Tuple[NvimApi, Any]])
def get_var(vim: StrictNvimApi, name: str) -> Do:
    value = yield vim.var(name)
    return (vim, value)


@do(Either[str, Tuple[NvimApi, Any]])
def set_var(vim: StrictNvimApi, name: str, rest: List[Any]) -> Do:
    value, rest1 = yield rest.uncons.to_either(f'no value specified for updating var `{name}`')
    return vim.append.vars((name, value)), None


def manipulate_vars(vim: StrictNvimApi, method: str, name: str, rest: List[Any]) -> Either[str, Tuple[NvimApi, Any]]:
    return (
        get_var(vim, name)
        if method == 'nvim_get_var' else
        set_var(vim, name, rest)
        if method == 'nvim_set_var' else
        Left(f'not a variable request')
    )


@do(Either[str, Tuple[NvimApi, Any]])
def variable_request(vim: StrictNvimApi, method: str, args: List[Any]) -> Do:
    name, rest = yield args.uncons.to_either('no variable name given')
    yield manipulate_vars(vim, method, name, rest)


class Tabpage(Dat['Tabpage']):

    def __init__(self, data: ExtType) -> None:
        self.data = data


class Window(Dat['Window']):

    def __init__(self, data: ExtType) -> None:
        self.data = data


class Buffer(Dat['Buffer']):

    def __init__(self, data: ExtType) -> None:
        self.data = data


__all__ = ('NvimApi', 'StrictNvimApi', 'Tabpage', 'Window', 'StrictNvimHandler')
