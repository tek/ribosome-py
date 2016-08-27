import neovim

from ribosome.request.base import (RequestHandler, MessageRequestHandler,
                                   JsonMessageRequestHandler)

from amino import Map


class Function(RequestHandler):

    @property
    def desc(self):
        return 'function'

    @property
    def default_kw(self):
        return Map(sync=True)

    @property
    def neovim_fun(self):
        @neovim.function(self.name, **self.kw)
        def neovim_fun_wrapper(obj, *rpc_args):
            return self.dispatch(obj, rpc_args)
        return neovim_fun_wrapper


class MessageFunction(Function, MessageRequestHandler):
    pass


class JsonMessageFunction(Function, JsonMessageRequestHandler):
    pass


def function(**kw):
    def neovim_fun_decorator(fun):
        handler = Function(fun, **kw)
        return handler.neovim_fun
    return neovim_fun_decorator


def msg_function(msg: type, **kw):
    def neovim_msg_fun_decorator(fun):
        handler = MessageFunction(fun, msg, **kw)
        return handler.neovim_fun
    return neovim_msg_fun_decorator


def json_msg_function(msg: type, **kw):
    def neovim_json_msg_fun_decorator(fun):
        handler = JsonMessageFunction(fun, msg, **kw)
        return handler.neovim_fun
    return neovim_json_msg_fun_decorator

__all__ = ('function', 'msg_function', 'json_msg_function')
