from typing import TypeVar, Callable, Generic, Any, Type

import toolz

from amino import Map, List, Either, _, Nil, Maybe, Boolean, __
from amino.dat import Dat
from amino.func import flip

from ribosome.nvim.io import NS
from ribosome.dispatch.data import DispatchResult
from ribosome.trans.handler import TransHandler, FreeTrans
from ribosome.request.handler.handler import RequestHandler, RequestHandlers
from ribosome.dispatch.mapping import Mappings

D = TypeVar('D')
CD = TypeVar('CD')
CC = TypeVar('CC')
TransState = NS[D, DispatchResult]


class NoComponentData(Dat['NoComponentData']):
    pass


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


class ComponentData(Generic[D, CD], Dat['ComponentData[D, CD]']):

    def __init__(self, main: D, comp: CD) -> None:
        self.main = main
        self.comp = comp


def comp_data() -> NS[ComponentData[D, CD], CD]:
    return NS.inspect(_.comp)


# FIXME reassignment
CD = TypeVar('CD', bound=ComponentData)


class Component(Generic[D, CD, CC], Dat['Component[D, CD, CC]']):

    @staticmethod
    def cons(
            name: str,
            request_handlers: List[RequestHandler]=Nil,
            handlers: List[TransHandler]=Nil,
            state_ctor: Callable[[], CD]=None,
            config: CC=None,
            mappings: Mappings=None,
    ) -> 'Component[D, CD, CC]':
        hs = message_handlers(handlers)
        return Component(
            name,
            RequestHandlers.cons(*request_handlers),
            hs,
            state_ctor or NoComponentData,
            Maybe.check(config),
            mappings or Mappings.cons(),
        )

    def __init__(
            self,
            name: str,
            request_handlers: RequestHandlers,
            handlers: Map[float, Handlers],
            state_ctor: Maybe[Callable[[D], CD]],
            config: Maybe[CC],
            mappings: Mappings,
    ) -> None:
        self.name = name
        self.request_handlers = request_handlers
        self.handlers = handlers
        self.state_ctor = state_ctor
        self.config = config
        self.mappings = mappings

    def handler_by_name(self, name: str) -> Either[str, TransHandler]:
        return self.handlers.find(_.name == name).to_either(f'component `{self.name}` has no handler `name`')

    def contains(self, handler: FreeTrans) -> Boolean:
        return self.request_handlers.trans_handlers.exists(_.fun == handler.fun)


class Components(Generic[D, CC], Dat['Components']):

    @staticmethod
    def cons(
            all: List[Component[D, Any, CC]]=Nil,
            config_type: Type[CC]=Any,
    ) -> 'Components[D, CC]':
        return Components(all, config_type)

    def __init__(self, all: List[Component[D, Any, CC]], config_type: Type[CC]) -> None:
        self.all = all
        self.config_type = config_type

    @property
    def has_config(self) -> Boolean:
        return self.config_type is not Any

    def by_name(self, name: str) -> Either[str, Component[D, CD, CC]]:
        return self.all.find(_.name == name).to_either(f'no component named {name}')

    @property
    def config(self) -> List[CC]:
        return self.all.collect(_.config)

    def for_handler(self, handler: FreeTrans) -> Maybe[Component]:
        return self.all.find(__.contains(handler))


__all__ = ('Component', 'Components')
