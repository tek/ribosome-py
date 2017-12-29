import inspect
from typing import Callable, Iterable, cast, Generator, TypeVar

from amino.options import env_xdg_data_dir
from amino import List, Either, Lists, Map, _, L, __, Path, Right, Try, Nil, Boolean, Left, Eval
from amino.func import flip
from amino.util.string import ToStr
from amino.do import do

from ribosome.nvim import NvimIO
from ribosome.logging import Logging
from ribosome.config.setting import Setting, EvalSetting, setting_ctor

A = TypeVar('A')
B = TypeVar('B')
state_dir_help_default = '''This directory is used to persist the plugin's current state.'''
state_dir_base_default = env_xdg_data_dir.value / Path | (Path.home() / '.local' / 'share')
proteome_name_help = 'If **proteome** is installed, the session name is obtained from the main project name.'
session_name_help = 'A custom session name for the state dir can be specified.'
components_help = '''The plugin can run an arbitrary set of sub-components that inherit the class `Component`.
They receive all messages the core of the plugin processes and have access to the plugin state.
They can define nvim request handlers with the decorator `trans.xyz`.
The entries of this setting can either be names of the builtin components or arbitrary python module paths that define
custom components.
'''


@do(Either[str, str])
def project_name_from_path() -> Generator:
    cwd = yield Try(Path.cwd)
    name = cwd.name
    yield Right(name) if name else Left('cwd broken')


@do(NvimIO[Either[str, Path]])
def state_dir_with_name(state_dir: Setting[Path], proteome_name: Setting[str],
                        session_name: Setting[str]) -> Generator:
    base = yield state_dir.value_or_default
    pro_name = yield proteome_name.value
    sess_name = yield session_name.value
    path = pro_name.o(sess_name).o(project_name_from_path) / (lambda a: base / a)
    yield NvimIO.pure(path)


class Settings(ToStr, Logging):

    def __init__(self, name: str, state_dir_help: str=state_dir_help_default) -> None:
        self.name = name
        self.components = list_setting('components', 'names or paths of active components', components_help, True,
                                       Right(Nil))
        self.state_dir = path_setting('state_dir', 'state persistence directory', state_dir_help, True,
                                      Right(state_dir_base_default / self.name))
        self.proteome_name = str_setting('proteome_main_name', 'project name from protoeome', proteome_name_help, False)
        self.session_name = str_setting('ribosome_session_name', 'project name from user var', session_name_help, False)
        self.project_state_dir = EvalSetting(
            'project_state_dir',
            Eval.always(lambda: state_dir_with_name(self.state_dir, self.proteome_name, self.session_name))
        )

    def all(self) -> Map[str, Setting]:
        settings = inspect.getmembers(self, L(isinstance)(_, Setting))
        return Map(Lists.wrap(settings).map(_[1]).apzip(_.name).map2(flip))

    def _arg_desc(self) -> List[str]:
        return List(str(self.all()))


def path_list(data: list) -> Either[str, List[Path]]:
    return Lists.wrap(data).traverse(lambda a: Try(Path, a) / __.expanduser(), Either)


str_setting = setting_ctor(str, lambda a: Right(a))
int_setting = setting_ctor(int, lambda a: Right(a))
float_setting = setting_ctor(float, lambda a: Right(a))
list_setting = setting_ctor(list, cast(Callable[[Iterable[A]], Either[str, List[B]]], (lambda a: Right(Lists.wrap(a)))))
path_setting = setting_ctor(str, (lambda a: Try(Path, a)))
path_list_setting = setting_ctor(list, path_list)
map_setting = setting_ctor(dict, lambda a: Right(Map(a)))
path_map_setting = setting_ctor(dict, lambda a: Try(Map, a).valmap(lambda b: Path(b).expanduser()))
bool_setting = setting_ctor(int, lambda a: Right(Boolean(a)))


__all__ = ('Settings', 'str_setting', 'float_setting', 'list_setting', 'path_setting', 'path_list_setting',
           'map_setting', 'path_map_setting', 'bool_setting')
