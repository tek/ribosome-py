import neovim

from amino import List, Map, L, __, _
from amino.util.string import snake_case

from ribosome.logging import log
from ribosome.unite.data import UniteSyntax


def _convert_candidate(c):
    return c if isinstance(c, dict) else {'word': c}


def mk_unite_candidates(Unite):
    def decorator(name):
        handler = getattr(Unite, '{}_candidates'.format(name))
        def uc_wrap(f):
            @neovim.function(handler, sync=True)
            def f_wrap(*a, **kw):
                return f(*a, **kw) / _convert_candidate
            return f_wrap
        return uc_wrap
    return decorator


def _unite_word(args, key):
    first = List.wrap(args).lift(0)
    candidates = (
        first.to_list.join
        if first.exists(lambda a: isinstance(a, list))
        else first
    )
    return candidates / Map // __.get(key)


def mk_unite_action(Unite):
    def decorator(name, key='word'):
        handler = getattr(Unite, name)
        def uc_wrap(f):
            @neovim.function(handler)
            def f_wrap(self, args):
                _unite_word(args, key) / L(f)(self, _) % self.state.send
            return f_wrap
        return uc_wrap
    return decorator


def _unite_function(name, msg, param_cb):
    @neovim.function(name, sync=True)
    def _unite_dispatcher(self, args):
        params = param_cb(List.wrap(args))
        params / UniteSyntax % self.state.send
    return _unite_dispatcher


def unite_plugin(name, names):
    sname = snake_case(name)
    syntax_name = '_{}_unite_syntax'.format(sname)
    def decorator(cls):
        def set_fun(name, msg, cb):
            try:
                setattr(cls, name, _unite_function(name, msg, cb))
            except Exception as e:
                log.error(e)
        syntax_cb = lambda args: args.tail // _.head / _['source'] / _['name']
        set_fun(syntax_name, UniteSyntax, syntax_cb)
        return cls
    return decorator

__all__ = ('mk_unite_candidates', 'mk_unite_action', 'unite_plugin')
