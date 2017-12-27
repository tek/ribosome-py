from typing import TypeVar, Callable, Generic

import toolz

from amino import Map, List, Either, _, Nil, Maybe, I
from amino.dat import Dat
from amino.func import flip

from ribosome.nvim.io import NS
from ribosome.dispatch.data import DispatchResult
from ribosome.trans.handler import TransHandler
from ribosome.request.handler.handler import RequestHandler, RequestHandlers

D = TypeVar('D')
C = TypeVar('C')
TransState = NS[D, DispatchResult]


class Handlers(Dat['Handlers']):

    def __init__(self, prio: int, handlers: Map[type, TransHandler]) -> None:
        self.prio = prio
        self.handlers = handlers

    def handler(self, msg):
        return self.handlers.get(type(msg))


def message_handlers(handlers: List[TransHandler]) -> Map[float, Handlers]:
    def create(prio, h):
        h = List.wrap(h).apzip(_.message).map2(flip)
        return prio, Handlers(prio, Map(h))
    return Map(toolz.groupby(_.prio, handlers)).map(create)


class ComponentData(Generic[D, C], Dat['ComponentData[D, C]']):

    def __init__(self, main: D, comp: C) -> None:
        self.main = main
        self.comp = comp


C = TypeVar('C', bound=ComponentData)


class Component(Generic[D, C], Dat['Component']):

    @staticmethod
    def cons(
            name: str,
            request_handlers: List[RequestHandler]=Nil,
            handlers: List[TransHandler]=Nil,
            state_ctor: Callable[[], C]=None,
    ) -> 'Component[D]':
        hs = message_handlers(handlers)
        return Component(
            name,
            RequestHandlers.cons(*request_handlers),
            hs,
            state_ctor or (lambda: None),
        )

    def __init__(self,
                 name: str,
                 request_handlers: RequestHandlers,
                 handlers: Map[float, Handlers],
                 state_ctor: Maybe[Callable[[D], C]],
                 ) -> None:
        self.name = name
        self.request_handlers = request_handlers
        self.handlers = handlers
        self.state_ctor = state_ctor


class Components(Dat['Components']):

    def __init__(self, all: List[Component]) -> None:
        self.all = all

    def by_name(self, name: str) -> Either[str, Component]:
        return self.all.find(_.name == name).to_either(f'no component named {name}')


__all__ = ('Component', 'Components')
