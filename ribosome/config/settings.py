from amino.options import env_xdg_data_dir
from amino import Either, Path, Right, Try, Nil, Left, Eval, Do
from amino.do import do
from amino.boolean import true

from ribosome.nvim.io.compute import NvimIO
from ribosome.config.setting import EvalSetting, list_setting, path_setting, str_setting, bool_setting
from ribosome.nvim.io.api import N
from ribosome.nvim.api.rpc import plugin_name


@do(Either[str, str])
def project_name_from_path() -> Do:
    cwd = yield Try(Path.cwd)
    name = cwd.name
    yield Right(name) if name else Left('cwd broken')


@do(NvimIO[Either[str, Path]])
def state_dir_with_name() -> Do:
    plugin = yield plugin_name()
    base = yield state_dir.value_or_default()
    pro_name = yield proteome_main_name.value
    sess_name = yield ribosome_session_name.value
    path = pro_name.o(sess_name).o(project_name_from_path) / (lambda a: base / plugin / a)
    yield N.pure(path)


state_dir_help = '''This directory is used to persist the plugin's current state.'''
state_dir_base_default = env_xdg_data_dir.value / Path | (Path.home() / '.local' / 'share')
proteome_name_help = 'If **proteome** is installed, the session name is obtained from the main project name.'
session_name_help = 'A custom session name for the state dir can be specified.'
components_help = '''The plugin can run an arbitrary set of sub-components that inherit the class `Component`.
They receive all messages the core of the plugin processes and have access to the plugin state.
They can define nvim request handlers with the decorator `@prog`.
The entries of this setting can either be names of the builtin components or arbitrary python module paths that define
custom components.
'''

components = list_setting('components', 'names or paths of active components', components_help, True, Right(Nil))
state_dir = path_setting('ribosome_state_dir', 'state persistence directory', state_dir_help, False,
                         Right(state_dir_base_default))
proteome_main_name = str_setting('proteome_main_name', 'project name from protoeome', proteome_name_help, False)
ribosome_session_name = str_setting('ribosome_session_name', 'project name from user var', session_name_help, False)
project_state_dir = EvalSetting('project_state_dir', Eval.always(state_dir_with_name))
run_internal_init = bool_setting('run_internal_init', 'run internal initialization handler', '', True, Right(true))


__all__ = ('components', 'state_dir', 'proteome_main_name', 'ribosome_session_name', 'project_state_dir',
           'run_internal_init')
