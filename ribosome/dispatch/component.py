from typing import TypeVar, Callable, Generic, Any, Type

from amino import List, Either, _, Nil, Maybe, Boolean, __
from amino.dat import Dat

from ribosome.nvim.io import NS
from ribosome.trans.handler import TransF
from ribosome.request.handler.handler import RequestHandler, RequestHandlers
from ribosome.dispatch.mapping import Mappings

D = TypeVar('D')
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


class Component(Generic[D, CD, CC], Dat['Component[D, CD, CC]']):

    @staticmethod
    def cons(
            name: str,
            request_handlers: List[RequestHandler]=Nil,
            state_ctor: Callable[[], CD]=None,
            config: CC=None,
            mappings: Mappings=None,
    ) -> 'Component[D, CD, CC]':
        return Component(
            name,
            RequestHandlers.cons(*request_handlers),
            state_ctor or NoComponentData,
            Maybe.check(config),
            mappings or Mappings.cons(),
        )

    def __init__(
            self,
            name: str,
            request_handlers: RequestHandlers,
            state_ctor: Maybe[Callable[[D], CD]],
            config: Maybe[CC],
            mappings: Mappings,
    ) -> None:
        self.name = name
        self.request_handlers = request_handlers
        self.state_ctor = state_ctor
        self.config = config
        self.mappings = mappings

    def handler_by_name(self, name: str) -> Either[str, TransF]:
        return self.handlers.find(_.name == name).to_either(f'component `{self.name}` has no handler `name`')

    def contains(self, handler: TransF) -> Boolean:
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

    def for_handler(self, handler: TransF) -> Maybe[Component]:
        return self.all.find(__.contains(handler))


__all__ = ('Component', 'Components')
