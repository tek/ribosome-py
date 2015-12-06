from typing import TypeVar, Any
from pathlib import Path

import neovim  # type: ignore

from tryp import Maybe, may, List, Map

from trypnv.log import VimLog, DebugLog


def quote(text):
    return text.replace('"', '\\"').replace("'", "''")

A = TypeVar('A')


class NvimFacade(object):

    def __init__(self, vim: neovim.Nvim) -> None:
        self.vim = vim

    @may
    def var(self, name) -> Maybe[str]:
        v = self.vim.vars.get(name)
        if v is None:
            Log.error('variable not found: {}'.format(name))
        return v

    def pvar(self, name) -> Maybe[str]:
        return self.var('proteome_{}'.format(name))

    def typed(self, tpe: type, value: Maybe[A]) -> Maybe[A]:
        @may
        def check(v: A):
            if isinstance(v, tpe):
                return v
            else:
                msg = 'invalid type {} for variable {} (wanted {})'.format(
                    type(v), v, tpe)
                Log.error(msg)
        return value.flatMap(check)

    def s(self, name):
        return self.typed(str, self.var(name))

    def ps(self, name):
        return self.typed(str, self.pvar(name))

    def l(self, name):
        return self.typed(list, self.var(name))\
            .map(List.wrap)

    def pl(self, name):
        return self.typed(list, self.pvar(name))\
            .map(List.wrap)

    def d(self, name):
        return self.typed(dict, self.var(name))\
            .map(Map.wrap)

    def pd(self, name):
        return self.typed(dict, self.pvar(name))\
            .map(Map.wrap)

    def echo(self, text: str):
        self.vim.command('echo "{}"'.format(quote(text)))

    def echohl(self, hl: str, text: str):
        cmd = 'echo "{}"'.format(quote(text))
        self.vim.command('echohl {} | ' + cmd + ' | echohl None'.format(hl))

    def echowarn(self, text: str):
        self.echohl('WarningMsg', text)

    def echoerr(self, text: str):
        self.echohl('ErrorMsg', text)

    def switch_root(self, path: Path):
        self.vim.command('cd {}'.format(path))


class LogFacade(object):

    _vim = None  # type: NvimFacade

    def log(self):
        return Maybe(Log._vim)\
            .map(lambda a: VimLog(a))\
            .get_or_else(DebugLog())

    def info(self, msg: Any):
        self.log().info(str(msg))

    def warn(self, msg: Any):
        self.log().warn(str(msg))

    def error(self, msg: Any):
        self.log().error(str(msg))

    def debug(self, msg: Any):
        self.log().debug(str(msg))

Log = LogFacade()  # type: LogFacade

__all__ = ['NvimFacade']
