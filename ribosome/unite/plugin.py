import neovim

from amino import List, Map, L, __, _


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

__all__ = ('mk_unite_candidates', 'mk_unite_action')
