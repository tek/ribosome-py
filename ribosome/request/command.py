import neovim

from ribosome.request.base import (RequestHandler, MessageRequestHandler,
                                   JsonMessageRequestHandler)


class Command(RequestHandler):

    @property
    def desc(self):
        return 'command'

    @property
    def neovim_cmd(self):
        @neovim.command(self.name, nargs=self.nargs, **self.kw)
        def neovim_cmd_wrapper(obj, *rpc_args):
            return self.dispatch(obj, rpc_args)
        return neovim_cmd_wrapper


class MessageCommand(Command, MessageRequestHandler):
    pass


class JsonMessageCommand(Command, JsonMessageRequestHandler):
    pass


class StateCommand(MessageCommand):

    def __init__(self, msg: type, **kw) -> None:
        def fun():
            pass
        super(StateCommand, self).__init__(fun, msg, **kw)

    def _call_fun(self, obj, *args):
        return self._message(*args)

    @property
    def _infer_name(self):
        return self._message.__name__


def command(**kw):
    def neovim_cmd_decorator(fun):
        handler = Command(fun, **kw)
        return handler.neovim_cmd
    return neovim_cmd_decorator


def msg_command(msg: type, **kw):
    def neovim_msg_cmd_decorator(fun):
        handler = MessageCommand(fun, msg, **kw)
        return handler.neovim_cmd
    return neovim_msg_cmd_decorator


def json_msg_command(msg: type, **kw):
    def neovim_json_msg_cmd_decorator(fun):
        handler = JsonMessageCommand(fun, msg, **kw)
        return handler.neovim_cmd
    return neovim_json_msg_cmd_decorator


__all__ = ('command', 'msg_command', 'json_msg_command')
