import abc
from typing import Any, Callable, Tuple

from neovim.msgpack_rpc import Session

from msgpack import ExtType

from amino import List, Either, Map, Left, Try, Dat


class NvimApi(Dat['NvimApi']):

    def __init__(self, name: str) -> None:
        self.name = name

    @abc.abstractmethod
    def request(self, method: str, args: List[Any]) -> Either[str, Tuple['NvimApi', Any]]:
        ...


class NativeNvimApi(NvimApi):

    def __init__(self, name: str, session: Session) -> None:
        self.name = name
        self.session = session

    def request(self, method: str, args: List[Any]) -> Either[str, Tuple['NvimApi', Any]]:
        return Try(self.session.request, method, *args) / (lambda a: (a, self))


class StrictNvimApi(NvimApi):

    def __init__(
            self,
            name: str,
            vars: Map[str, Any],
            request_handler: Callable[['StrictNvimApi', str, List[Any]], Either[List[str], Tuple['NvimApi', Any]]],
    ) -> None:
        self.name = name
        self.vars = vars
        self.request_handler = request_handler

    def request(self, method: str, args: List[Any]) -> Either[str, Tuple['NvimApi', Any]]:
        return self.request_handler(self, method, args).accum_error_lift(self.try_var, method, args)

    def try_var(self, method: str, args: List[Any]) -> Either[str, Any]:
        return (
            args
            .detach_head
            .to_either('no variable name given')
            .flat_map2(lambda h, t: self.var(h))
            .map(lambda a: (self, a))
            if method == 'nvim_get_var' else
            Left(f'not a variable request')
        )

    def var(self, name: str) -> Either[str, Any]:
        return self.vars.lift(name).to_either(f'no variable `{name}` defined')


class Tabpage(Dat['Tabpage']):

    def __init__(self, data: ExtType) -> None:
        self.data = data


class Window(Dat['Window']):

    def __init__(self, data: ExtType) -> None:
        self.data = data


class Buffer(Dat['Buffer']):
    def __init__(self, data: ExtType) -> None:
        self.data = data


__all__ = ('NvimApi', 'NativeNvimApi', 'StrictNvimApi', 'Tabpage', 'Window')
