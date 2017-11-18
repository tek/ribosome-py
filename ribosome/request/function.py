import neovim

from ribosome.request.legacy import LegacyRequestHandler
from ribosome.request.handler.method import RpcMethod, FunctionMethod

from amino import Map


class Function(LegacyRequestHandler):

    @property
    def desc(self):
        return 'function'

    @property
    def default_kw(self):
        return Map(sync=True)

    @property
    def neovim_fun(self):
        @neovim.function(self.vim_name, **self.kw)
        def neovim_fun_wrapper(obj, *rpc_args):
            return self.dispatch(obj, rpc_args)
        return neovim_fun_wrapper

    @property
    def method(self) -> RpcMethod:
        return FunctionMethod()


def function(**kw):
    def neovim_fun_decorator(fun):
        handler = Function(fun, **kw)
        fun.spec = handler.spec
        nfun = handler.neovim_fun
        nfun.spec = handler.spec
        return nfun
    return neovim_fun_decorator

__all__ = ('function',)
