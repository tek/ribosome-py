import abc
from typing import Callable, Type, TypeVar, Generic, Generator

from amino import List, Either, __, Left, Eval
from amino.util.string import ToStr
from amino.do import do

from ribosome.nvim import NvimIO
from ribosome.nvim.components import NvimComponent
from ribosome.logging import Logging

A = TypeVar('A', contravariant=True)
B = TypeVar('B')


class PluginSetting(Generic[B], Logging, ToStr):

    @abc.abstractproperty
    def value(self) -> NvimIO[Either[str, B]]:
        ...

    @abc.abstractproperty
    def default_e(self) -> Either[str, B]:
        ...

    @property
    def value_or_default(self) -> NvimIO[B]:
        @do(NvimIO[B])
        def run() -> Generator:
            value = yield self.value
            yield NvimIO.from_either(value.o(self.default_e))
        return run()


class StrictSetting(Generic[A, B], PluginSetting[B]):

    def __init__(
            self,
            name: str,
            desc: str,
            help: str,
            prefix: bool,
            tpe: Type[A],
            ctor: Callable[[A], B],
            default: Either[str, B],
    ) -> None:
        self.name = name
        self.desc = desc
        self.help = help
        self.prefix = prefix
        self.tpe = tpe
        self.ctor = ctor
        self.default = default

    @property
    def value(self) -> NvimIO[Either[str, B]]:
        @do(Either[str, B])
        def read(v: NvimComponent) -> Generator:
            vars = v.vars
            getter = vars.p if self.prefix else vars
            raw = yield vars.typed(self.tpe, getter(self.name))
            yield self.ctor(raw)
        return NvimIO.delay(read)

    def value_or(self, default: B) -> NvimIO[B]:
        return self.value / __.get_or_else(default)

    @property
    def default_e(self) -> Either[str, B]:
        return self.default

    def _arg_desc(self) -> List[str]:
        return List(self.name, str(self.prefix), str(self.tpe))


class EvalSetting(Generic[B], PluginSetting[B]):

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


def setting_ctor(tpe: Type[A], ctor: Callable[[A], B]) -> Callable[[str, str, str, bool, B], PluginSetting[B]]:
    def setting(name: str, desc: str, help: str, prefix: bool, default: Either[str, B]=Left('no default specified')
                ) -> PluginSetting[B]:
        return StrictSetting(name, desc, help, prefix, tpe, ctor, default)
    return setting


__all__ = ('PluginSetting', 'StrictSetting', 'EvalSetting', 'setting_ctor')
