import abc
from typing import Any, Callable

from neovim.msgpack_rpc import Session

from msgpack import ExtType

from amino import List, Either, Map, Left, Try, Dat


class NvimApi(abc.ABC):

    def __init__(self, name: str) -> None:
        self.name = name

    @abc.abstractmethod
    def request(self, method: str, args: List[Any]) -> Any:
        ...


NvimApi = NvimApi


class NativeNvimApi(NvimApi):

    def __init__(self, name: str, session: Session) -> None:
        self.name = name
        self.session = session

    def request(self, name: str, args: List[Any]) -> Either[str, Any]:
        return Try(self.session.request, name, *args)


class StrictNvimApi(NvimApi):

    def __init__(
            self,
            name: str,
            vars: Map[str, Any],
            request_handler: Callable[[str, List[Any]], Either[List[str], Any]],
    ) -> None:
        self.name = name
        self.vars = vars
        self.request_handler = request_handler

    def request(self, method: str, args: List[Any]) -> Either[str, Any]:
        return self.request_handler(method, args).accum_error_lift(self.try_var, method, args)

    def try_var(self, method: str, args: List[Any]) -> Either[str, Any]:
        return (
            args.detach_head.to_either('no variable name given').flat_map2(lambda h, t: self.var(h))
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
