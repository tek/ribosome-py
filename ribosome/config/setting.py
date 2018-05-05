import abc
from typing import Callable, Type, TypeVar, Generic, Any

from amino import List, Either, __, Left, Eval, ADT, Right, Try, Path, Map, Boolean, Lists
from amino.do import do, Do
from amino.boolean import false, true

from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.api.variable import variable_prefixed, variable, variable_set, variable_set_prefixed
from ribosome.nvim.api.util import cons_checked_e
from ribosome.nvim.io.api import N

A = TypeVar('A', contravariant=True)
B = TypeVar('B')


class Setting(Generic[B], ADT['Setting[B]']):

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
        yield current.cata(lambda e: self.update(fallback), lambda a: N.unit)

    @property
    def value_or_default(self) -> NvimIO[B]:
        @do(NvimIO[B])
        def run() -> Do:
            value = yield self.value
            yield N.from_either(value.o(self.default_e))
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
        api_call = variable_prefixed if self.prefix else variable
        return api_call(self.name, cons_checked_e(self.tpe, self.ctor))

    def value_or(self, default: B) -> NvimIO[B]:
        return self.value / __.get_or_else(default)

    @property
    def default_e(self) -> Either[str, B]:
        return self.default

    def update(self, value: B) -> NvimIO[None]:
        api_call = variable_set_prefixed if self.prefix else variable_set
        return api_call(self.name, value)


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
        return N.pure(None)


SettingCtor = Callable[[str, str, str, bool, Either[str, B]], Setting[B]]
no_default: Either[str, Any] = Left('no default specified')


def setting_ctor(tpe: Type[A], ctor: Callable[[A], Either[str, B]]) -> SettingCtor:
    def setting(name: str, desc: str, help: str, prefix: bool, default: Either[str, B]=no_default) -> Setting[B]:
        return StrictSetting(name, desc, help, prefix, tpe, ctor, default)
    return setting


def path_list(data: list) -> Either[str, List[Path]]:
    return Lists.wrap(data).traverse(lambda a: Try(Path, a) / __.expanduser(), Either)


str_setting = setting_ctor(str, Right)
int_setting = setting_ctor(int, Right)
float_setting = setting_ctor(float, Right)
list_setting = setting_ctor(list, Right)
path_setting = setting_ctor(str, (lambda a: Try(Path, a)))
path_list_setting = setting_ctor(list, path_list)
map_setting = setting_ctor(dict, lambda a: Right(Map(a)))
path_map_setting = setting_ctor(dict, lambda a: Try(Map, a).valmap(lambda b: Path(b).expanduser()))
bool_setting = setting_ctor(int, lambda a: Right(false if a == 0 else true))


__all__ = ('Setting', 'StrictSetting', 'EvalSetting', 'setting_ctor', 'str_setting', 'int_setting', 'float_setting',
           'list_setting', 'path_setting', 'path_list_setting', 'map_setting', 'path_map_setting', 'bool_setting')
