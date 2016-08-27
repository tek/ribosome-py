from typing import Callable, Any, Tuple
import json

import neovim

from amino import may, Map, Try

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


class JsonMessageCommand(MessageCommand):

    def __init__(self, fun: Callable[[], Any], msg: type, **kw) -> None:
        super(JsonMessageCommand, self).__init__(fun, msg, **kw)

    @property
    def nargs(self):
        return '+'

    @property
    def min(self) -> int:
        return super().min - 1

    @property  # type: ignore
    @may
    def max(self):
        pass

    def _extract_args(self, args: Tuple[str]):
        def parse(d):
            def fail(err):
                raise ParseError('neither valid json nor python: {}'.format(d))
            return (
                Try(json.loads, d)
                .or_else(Try(eval, d))
                .or_else(Try(json.loads, d.replace('\\"', '"')))
                .right_or_map(fail)
            )
        pos_args, data_args = (tuple(args[:self.min]),  # type: ignore
                               tuple(args[self.min:]))  # type: ignore
        data = ' '.join(data_args)
        params = parse(data) if data else {}
        return pos_args + (Map(params),)

    def _call_fun(self, obj, *args):
        try:
            real_args = self._extract_args(args)
        except ParseError as e:
            self.log.error(e)
        else:
            super(JsonMessageCommand, self)._call_fun(obj, *real_args)


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
