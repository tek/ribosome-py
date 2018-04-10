from typing import TypeVar, Callable, Generic, Any, Type, Union

from amino import List, Either, _, Nil, Maybe, Boolean, __, Map
from amino.dat import Dat

from ribosome.request.handler.handler import RequestHandler, RequestHandlers
from ribosome.nvim.io.state import NS
from ribosome.data.mapping import Mappings

# FIXME typevar P is temporary
D = TypeVar('D')
P = TypeVar('P')
CC = TypeVar('CC')
CD = TypeVar('CD')


class NoComponentData(Dat['NoComponentData']):
    pass


class ComponentData(Generic[D, CD], Dat['ComponentData[D, CD]']):

    def __init__(self, main: D, comp: CD) -> None:
        self.main = main
        self.comp = comp


def comp_data() -> NS[ComponentData[D, CD], CD]:
    return NS.inspect(_.comp)


def infer_state_ctor(state_type: Union[None, Type[CD]]) -> Union[None, Callable[[], CD]]:
    return (
        None
        if state_type is None else
        getattr(state_type, 'cons', state_type)
    )


class Component(Generic[D, CD, CC], Dat['Component[D, CD, CC]']):

    @staticmethod
    def cons(
            name: str,
            request_handlers: List[RequestHandler]=Nil,
            trans_handlers: List[RequestHandler]=Nil,
            state_type: Type[CD]=None,
            state_ctor: Callable[[], CD]=None,
            config: CC=None,
            mappings: Mappings=None,
    ) -> 'Component[D, CD, CC]':
        return Component(
            name,
            RequestHandlers.cons(*request_handlers),
            RequestHandlers.cons(*trans_handlers),
            state_type or NoComponentData,
            state_ctor or infer_state_ctor(state_type) or NoComponentData,
            Maybe.check(config),
            mappings or Mappings.cons(),
        )

    def __init__(
            self,
            name: str,
            request_handlers: RequestHandlers,
            trans_handlers: RequestHandlers,
            state_type: Type[CD],
            state_ctor: Maybe[Callable[[D], CD]],
            config: Maybe[CC],
            mappings: Mappings,
    ) -> None:
        self.name = name
        self.request_handlers = request_handlers
        self.trans_handlers = trans_handlers
        self.state_type = state_type
        self.state_ctor = state_ctor
        self.config = config
        self.mappings = mappings

    def handler_by_name(self, name: str) -> Either[str, P]:
        return self.handlers.find(_.name == name).to_either(f'component `{self.name}` has no handler `name`')

    def contains(self, handler: P) -> Boolean:
        return self.request_handlers.trans_handlers.exists(_.fun == handler.fun)


class Components(Generic[D, CC], Dat['Components']):

    @staticmethod
    def cons(
            all: List[Component[D, Any, CC]]=Nil,
    ) -> 'Components[D, CC]':
        return Components(all)

    def __init__(self, all: List[Component[D, Any, CC]]) -> None:
        self.all = all

    def by_name(self, name: str) -> Either[str, Component[D, CD, CC]]:
        return self.all.find(_.name == name).to_either(f'no component named {name}')

    def by_type(self, tpe: type) -> Either[str, Component[D, CD, CC]]:
        return self.all.find(_.state_type == tpe).to_either(f'no component with state type {tpe}')

    @property
    def config(self) -> List[CC]:
        return self.all.collect(_.config)

    def for_handler(self, handler: P) -> Maybe[Component]:
        return self.all.find(__.contains(handler))


class ComponentConfig(Dat['ComponentConfig']):

    @staticmethod
    def cons(
            available: Map[str, Component[D, Any, CC]],
    ) -> 'ComponentConfig':
        return ComponentConfig(
            available,
        )

    def __init__(self, available: Map[str, Component[D, Any, CC]]) -> None:
        self.available = available


__all__ = ('Component', 'Components')
