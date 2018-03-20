import abc
from typing import Callable, Type, TypeVar, Generic, Generator

from amino import List, Either, __, Left, Eval
from amino.util.string import ToStr
from amino.do import do, Do

from ribosome.nvim import NvimIO, NvimFacade
from ribosome.logging import Logging

A = TypeVar('A', contravariant=True)
B = TypeVar('B')


class Setting(Generic[B], Logging, ToStr):

    @abc.abstractproperty
    def value(self) -> NvimIO[Either[str, B]]:
        ...

    @abc.abstractproperty
    def default_e(self) -> Either[str, B]:
        ...

    @abc.abstractmethod
    def update(self, value: B) -> NvimIO[None]:
        ...

    @do(NvimIO[None])
    def ensure(self, fallback: B) -> Do:
        current = yield self.value
        yield current.cata(lambda e: self.update(fallback), lambda a: NvimIO.unit)

    @property
    def value_or_default(self) -> NvimIO[B]:
        @do(NvimIO[B])
        def run() -> Generator:
            value = yield self.value
            yield NvimIO.from_either(value.o(self.default_e))
        return run()


class StrictSetting(Generic[A, B], Setting[B]):

    def __init__(
            self,
            name: str,
            desc: str,
            help: str,
            prefix: bool,
            tpe: Type[A],
            ctor: Callable[[A], Either[str, B]],
            default: Either[str, B],
    ) -> None:
        self.name = name
        self.desc = desc
        self.help = help
        self.prefix = prefix
        self.tpe = tpe
        self.ctor = ctor
        self.default = default

    def _arg_desc(self) -> List[str]:
        return List(self.name, str(self.prefix), str(self.tpe))

    @property
    def value(self) -> NvimIO[Either[str, B]]:
        @do(Either[str, B])
        def read(v: NvimFacade) -> Do:
            self.log.debug(f'request variable `{self.name}`')
            getter = v.sync_vars.p if self.prefix else v.sync_vars.get
            untyped = getter(self.name)
            raw = yield v.sync_vars.typed(self.tpe, untyped)
            self.log.debug(f'variable `{self.name}`: {raw}')
            yield self.ctor(raw)
        return NvimIO.delay(read)

    def value_or(self, default: B) -> NvimIO[B]:
        return self.value / __.get_or_else(default)

    @property
    def default_e(self) -> Either[str, B]:
        return self.default

    def update(self, value: B) -> NvimIO[None]:
        def write(v: NvimFacade) -> NvimIO[None]:
            setter = v.sync_vars.set_p if self.prefix else v.sync_vars.set
            setter(self.name, value)
        return NvimIO.delay(write)


class EvalSetting(Generic[B], Setting[B]):

    def __init__(
            self,
            name: str,
            f: Eval[NvimIO[Either[str, B]]],
            default: Either[str, B]=Left('no default specified')
    ) -> None:
        self.name = name
        self.f = f
        self.default = default

    def _arg_desc(self) -> List[str]:
        return List(self.name)

    @property
    def value(self) -> NvimIO[Either[str, B]]:
        return self.f.value

    @property
    def default_e(self) -> Either[str, B]:
        return self.default

    def update(self, value: B) -> NvimIO[None]:
        return NvimIO.pure(None)


def setting_ctor(tpe: Type[A], ctor: Callable[[A], B]) -> Callable[[str, str, str, bool, B], Setting[B]]:
    def setting(name: str, desc: str, help: str, prefix: bool, default: Either[str, B]=Left('no default specified')
                ) -> Setting[B]:
        return StrictSetting(name, desc, help, prefix, tpe, ctor, default)
    return setting


__all__ = ('Setting', 'StrictSetting', 'EvalSetting', 'setting_ctor')
