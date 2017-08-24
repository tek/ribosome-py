from functools import wraps
from typing import Callable, Any

from amino import env


def unite(f: Callable[[Any, str], None]) -> Callable[[Any], None]:
    @wraps(f)
    def wrapper(self: Any) -> None:
        def go(unite: str) -> Any:
            self.vim.options.amend_l('rtp', [unite])
            self.vim.cmd('source {}/plugin/*.vim'.format(unite))
            self.vim.cmd('source {}/plugin/unite/*.vim'.format(unite))
            self.vim.cmd('source {}/syntax/*.vim'.format(unite))
            return f(self)
        return env['UNITE_DIR'] / go | None
    return wrapper

__all__ = ('unite',)
