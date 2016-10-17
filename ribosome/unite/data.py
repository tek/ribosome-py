import abc

from ribosome.machine import Message
from ribosome import NvimFacade
from ribosome.logging import Logging

from amino import List, Map, _, L


class UniteMessage(Message, varargs='unite_args'):
    pass


class UniteEntity(Logging, metaclass=abc.ABCMeta):
    ''' set up sources and kinds dynamically.
    The python call API cannot be used, as funcrefs cannot be
    serialized.
    The callback functions must be called once so that exists()
    can see them, otherwise Unite refuses to work.
    They must be called a/sync according to their definition,
    otherwise it will silently deadlock!
    '''

    def __init__(self, name: str) -> None:
        self.name = name

    @abc.abstractproperty
    def tpe(self):
        ...

    @abc.abstractproperty
    def data(self):
        ...

    @property
    def _func_defs_sync(self):
        return List()

    @property
    def _func_defs_async(self):
        return List()

    def _force_function_defs(self, vim):
        force = lambda c, n: c('silent call {}()'.format(n))
        self._func_defs_sync.foreach(L(force)(vim.cmd_sync, _))
        self._func_defs_async.foreach(L(force)(vim.cmd, _))

    def define(self, vim: NvimFacade):
        self._force_function_defs(vim)
        vim.cmd('call unite#define_{}({})'.format(self.tpe, self.data))


class UniteSource(UniteEntity):
    _templ = '''
    {{
        'name': '{}',
        'gather_candidates': function('{}'),
        'default_kind': '{}',
    }}
    '''.replace('\n', '')

    def __init__(self, name: str, source: str, kind: str) -> None:
        super().__init__(name)
        self.source = source
        self.kind = kind

    @property
    def tpe(self):
        return 'source'

    @property
    def _func_defs_sync(self):
        return List(self.source)

    @property
    def data(self):
        return self._templ.format(self.name, self.source, self.kind)


class UniteKind(UniteEntity):
    _templ = '''
    {{
        'name': '{name}',
        'default_action': '{default}',
        'parents': [],
        'action_table': {{
            {actions}
        }}
    }}
    '''.replace('\n', '')

    _action_templ = '''
    '{name}': {{
        'func': function('{handler}'),
        'description': '{desc}',
        'is_selectable': '{is_selectable}',
    }}
    '''.replace('\n', '')

    _defaults = Map(is_selectable=1)

    @property
    def tpe(self):
        return 'kind'

    def __init__(self, name: str, actions: List[Map]) -> None:
        super().__init__(name)
        self.actions = actions / self._defaults.merge
        self.default = actions.head / _['name'] | 'none'

    @property
    def _func_defs_async(self):
        return self.actions / _['handler']

    def _action(self, params):
        return self._action_templ.format(**params)

    @property
    def data(self):
        actions = self.actions.map(self._action).mk_string(', ')
        return self._templ.format(name=self.name, actions=actions,
                                  default=self.default)

__all__ = ('UniteMessage', 'UniteEntity', 'UniteSource', 'UniteKind')
