import functools

import neovim

from ribosome.request.legacy import LegacyRequestHandler
from ribosome.request.handler.method import RpcMethod, CmdMethod


class Command(LegacyRequestHandler):

    @property
    def desc(self):
        return 'command'

    @property
    def neovim_cmd(self):
        @neovim.command(self.vim_name, nargs=self.nargs, **self.kw)
        @functools.wraps(self._fun)
        def neovim_cmd_wrapper(obj, *rpc_args):
            return self.dispatch(obj, rpc_args)
        return neovim_cmd_wrapper

    @property
    def method(self) -> RpcMethod:
        return CmdMethod()


def command(**kw):
    def neovim_cmd_decorator(fun):
        handler = Command(fun, **kw)
        ncmd = handler.neovim_cmd
        ncmd.spec = handler.spec
        return ncmd
    return neovim_cmd_decorator


__all__ = ('command',)
