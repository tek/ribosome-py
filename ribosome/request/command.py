import functools

import neovim

from ribosome.request.base import RequestHandler1
from ribosome.request.handler import RequestDispatcher, Cmd


class Command(RequestHandler1):

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
    def dispatcher(self) -> RequestDispatcher:
        return Cmd(self._fun)


def command(**kw):
    def neovim_cmd_decorator(fun):
        handler = Command(fun, **kw)
        ncmd = handler.neovim_cmd
        ncmd.spec = handler.spec
        return ncmd
    return neovim_cmd_decorator


__all__ = ('command',)
