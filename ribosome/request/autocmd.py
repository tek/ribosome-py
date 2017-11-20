import functools
from typing import TypeVar, Callable

import neovim

from ribosome.request.legacy import LegacyRequestHandler
from ribosome.trans.message_base import Message
from ribosome.request.handler.method import RpcMethod, AutocmdMethod

M = TypeVar('M', bound=Message)


class Autocmd(LegacyRequestHandler):

    @property
    def desc(self) -> str:
        return 'autocmd'

    @property
    def neovim_autocmd(self) -> Callable:
        @neovim.autocmd(self.vim_name, **self.kw)
        @functools.wraps(self._fun)
        def neovim_autocmd_wrapper(obj, *rpc_args):
            return self.dispatch(obj, rpc_args)
        return neovim_autocmd_wrapper

    @property
    def method(self) -> RpcMethod:
        return AutocmdMethod()


def autocmd(**kw):
    def neovim_autocmd_decorator(fun):
        handler = Autocmd(fun, **kw)
        fun = handler.neovim_autocmd
        fun.spc = handler.spec
        return fun
    return neovim_autocmd_decorator

__all__ = ('autocmd',)
