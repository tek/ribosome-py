import functools
from typing import TypeVar, Generic, Callable, Type

import neovim

from ribosome.request.base import RequestHandler, MessageRequestHandler, JsonMessageRequestHandler
from ribosome.machine.message_base import Message

M = TypeVar('M', bound=Message)


class Autocmd(RequestHandler):

    @property
    def desc(self) -> str:
        return 'autocmd'

    @property
    def neovim_autocmd(self) -> Callable:
        @neovim.autocmd(self.name, **self.kw)
        @functools.wraps(self._fun)
        def neovim_autocmd_wrapper(obj, *rpc_args):
            return self.dispatch(obj, rpc_args)
        return neovim_autocmd_wrapper


class MessageAutocmd(Generic[M], Autocmd, MessageRequestHandler[M]):
    pass


class JsonMessageAutocmd(Generic[M], Autocmd, JsonMessageRequestHandler[M]):
    pass


class StateAutocmd(Generic[M], MessageAutocmd):

    def __init__(self, msg: Type[M], **kw) -> None:
        def unit() -> None:
            pass
        super().__init__(unit, msg, **kw)

    def _call_fun(self, obj, *args, **kw):
        return self._message(*args, **kw)

    @property
    def _infer_name(self):
        return self._message.__name__


def autocmd(**kw):
    def neovim_autocmd_decorator(fun):
        handler = Autocmd(fun, **kw)
        return handler.neovim_autocmd
    return neovim_autocmd_decorator


def msg_autocmd(msg: type, **kw):
    def neovim_msg_autocmd_decorator(fun):
        handler = MessageAutocmd(fun, msg, **kw)
        return handler.neovim_autocmd
    return neovim_msg_autocmd_decorator


__all__ = ('autocmd', 'msg_autocmd')
