from typing import Callable, Any
from functools import wraps
import inspect

import neovim  # type: ignore

from fn import _  # type: ignore

from tryp import List, Maybe, may, Just

from trypnv.logging import log

from tek.tools import camelcaseify  # type: ignore

import trypnv


def try_int(val):
    return int(val) if isinstance(val, str) and str.isdigit() else val


def numeric(val):
    return isinstance(val, int)


class Command(object):

    def __init__(
            self,
            fun: Callable[..., Any],
            name: str=None,
            nargs=None,
            min: int=None,
            max: int=None,
            **kw
    ) -> None:
        self._fun = fun
        self._argspec = inspect.getfullargspec(fun)  # type: ignore
        self._params = List.wrap(self._argspec.args)
        self._param_count = self._params.length - (
            1 if self._params.head.contains('self') else 0
        )
        self._name = Maybe(name)
        self._nargs = Maybe(try_int(nargs))
        self._min = Maybe(min)
        self._max = Maybe(max)
        self._kw = kw

    @property
    def nargs(self):
        return self._nargs\
            .map(lambda a: '+' if numeric(a) and a > 1 else a)\
            .get_or_else(self._infer_nargs)

    @property
    def _infer_nargs(self):
        if self.min > 1:
            return '+'
        elif self.min == 1:
            return 1 if self.max.contains(1) else '+'
        else:
            if self.max.contains(0):
                return 0
            if self.max.contains(1):
                return '?'
            else:
                return '*'

    @property
    def min(self):
        return self._min.get_or_else(self._infer_min)

    @property
    def _infer_min(self):
        s = self._argspec
        return self._param_count - len(s.defaults or [])

    @property
    def max(self):
        return self._max.or_else(self._infer_max)

    @property  # type: ignore
    @may
    def _infer_max(self):
        s = self._argspec
        if not (s.varargs or s.varkw):
            return self._param_count

    @property
    def name(self):
        return self._name.get_or_else(self._infer_name)

    @property
    def _infer_name(self):
        return camelcaseify(self._fun.__name__)

    @property  # type: ignore
    @may
    def exact_count(self):
        if self.max.contains(self.min):
            return self.min

    def check_length(self, args):
        l = len(args)
        return (
            self.min <= l and
            not self.max.exists(_ < l)
        )

    @property
    def count_spec(self):
        return self.exact_count\
            .map(lambda a: 'exactly {}'.format(a) if a else 'none')\
            .get_or_else(
                Just(self.min)
                .zip(self.max)
                .smap('between {} and {}'.format)
                .get_or_else('at least {}'.format(self.min))
            )

    def error(self, args):
        msg = 'argument count for command "{}" is {}, must be {} ({})'
        err = msg.format(self.name, len(args), self.count_spec, args)
        log.error(err)
        return err

    def _call_fun(self, obj, *args):
        return self._fun(obj, *args)

    def dispatch(self, obj, rpc_args):
        args = List.wrap(rpc_args).lift(0).get_or_else(List())
        if self.check_length(args):
            return self._call_fun(obj, *args)
        else:
            return self.error(args)

    @property
    def neovim_cmd(self):
        @neovim.command(self.name, nargs=self.nargs, **self._kw)
        def neovim_cmd_wrapper(obj, *rpc_args):
            return self.dispatch(obj, rpc_args)
        return neovim_cmd_wrapper


class MessageCommand(Command):

    def __init__(self, fun: Callable[..., Any], msg: type, **kw) -> None:
        self._message = msg
        self._fun_name = fun.__name__
        super(MessageCommand, self).__init__(
            self._message.__class__.__init__, **kw)  # type: ignore

    @property
    def _infer_name(self):
        return camelcaseify(self._fun_name)

    def _call_fun(self, obj, *args):
        if isinstance(obj, trypnv.NvimStatePlugin):
            obj.state().send(self._message(*args))
        else:
            msg = 'msg_command can only be used on NvimStatePlugin ({})'
            log.error(msg.format(obj))

    @property
    def msg_dispatch(self):
        def msg_dispatch_wrapper(obj, *rpc_args):
            return self.dispatch(obj, rpc_args)
        return msg_dispatch_wrapper


class StateCommand(MessageCommand):

    def __init__(self, msg: type, **kw) -> None:
        def fun():
            pass
        super(StateCommand, self).__init__(fun, msg, **kw)

    def _call_fun(self, obj, *args):
        return self._message(*args)


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


__all__ = ['command', 'msg_command']
