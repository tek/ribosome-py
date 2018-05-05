from typing import Callable, Any, Union, List as TList

from amino import List, Map, L, __, _
from amino.util.string import snake_case

from ribosome.logging import log
from ribosome.unite.data import UniteSyntax


def _convert_candidate(c: Union[str, dict]) -> dict:
    return c if isinstance(c, dict) else {'word': c}


def mk_unite_candidates(Unite: type) -> Callable[[str], Callable[[Callable], Callable]]:
    def decorator(name: str) -> Callable:
        handler = getattr(Unite, '{}_candidates'.format(name))
        def uc_wrap(f: Callable) -> Callable:
            @neovim.function(handler, sync=True)
            def f_wrap(self: Any, args: list) -> List[dict]:
                return f(self, args) / _convert_candidate
            return f_wrap
        return uc_wrap
    return decorator


def _unite_word(args: TList[TList[dict]], key: str) -> str:
    first = List.wrap(args).lift(0)
    candidates = (
        first.to_list.join
        if first.exists(lambda a: isinstance(a, list))
        else first
    )
    return candidates / Map // __.get(key)


def mk_unite_action(Unite: type) -> Callable[[str, str], Callable[[Callable], Callable]]:
    def decorator(name: str, key: str='word') -> Callable[[Callable], Callable]:
        handler = getattr(Unite, name)
        def ua_wrap(f: Callable) -> Callable:
            @neovim.function(handler)
            def f_wrap(self: Any, args: list) -> None:
                _unite_word(args, key) / L(f)(self, _) % self.state().send
            return f_wrap
        return ua_wrap
    return decorator


def _unite_function(name: str, msg: type, param_cb: Callable) -> Callable:
    @neovim.function(name, sync=True)
    def _unite_dispatcher(self: Any, args: list) -> None:
        params = param_cb(List.wrap(args))
        params / UniteSyntax % self.state().send
    return _unite_dispatcher


def unite_plugin(pname: str) -> Callable[[type], type]:
    sname = snake_case(pname)
    syntax_name = '_{}_unite_syntax'.format(sname)
    def decorator(cls: type) -> type:
        def set_fun(fname: str, msg: type, cb: Callable) -> None:
            try:
                setattr(cls, fname, _unite_function(fname, msg, cb))
            except Exception as e:
                log.caught_exception_error(f'calling unite function {fname}', e)
        syntax_cb = lambda args: args.tail // _.head / __['source'] / __['pname']
        set_fun(syntax_name, UniteSyntax, syntax_cb)
        return cls
    return decorator


__all__ = ('mk_unite_candidates', 'mk_unite_action', 'unite_plugin')
