import logging
from typing import TypeVar, Callable, Union

from toolz import merge

import amino
from amino.lazy import lazy
import amino.logging
from amino.logging import (amino_logger, init_loglevel, amino_root_file_logging, DDEBUG, print_log_info, VERBOSE,
                           LazyRecord, TEST, log_stamp, module_log)
from amino import Path, Logger, Nothing, Maybe, List, Lists

import ribosome  # noqa
from ribosome import options
from ribosome.nvim.api.ui import echo
from ribosome.util.string import escape_dquote

alog = module_log()
A = TypeVar('A')


def fmt_echo(text: Union[str, List[str]], cmd: str='echom', prefix: Maybe[str]=Nothing) -> List[str]:
    lines = text if isinstance(text, List) else Lists.lines(str(text))
    pre = prefix.map(_ + ': ') | ''
    return lines.map(lambda a: '{} "{}{}"'.format(cmd, pre, escape_dquote(a)))


def fmt_echohl(text: Union[str, List[str]], hl: str, prefix: Maybe[str]=Nothing) -> List[str]:
    return echo(text, prefix=prefix).cons(f'echohl {hl}').cat('echohl None')


class NvimHandler(logging.Handler):

    def __init__(self, vim: 'ribosome.NvimApi') -> None:
        self.vim = vim
        self.dispatchers = {
            logging.INFO: self.echo,
            logging.WARN: self.echowarn,
            logging.ERROR: self.echoerr,
            logging.CRITICAL: self.echoerr,
        }
        super().__init__()

    def emit(self, record: LazyRecord) -> None:
        dispatcher = self.dispatchers.get(record.levelno, self.echom)
        dispatcher(record.short())

    def echo(self, msg: str) -> None:
        echo(msg).unsafe(self.vim)

    def echowarn(self, msg: str) -> None:
        echo(msg).unsafe(self.vim)

    def echoerr(self, msg: str) -> None:
        echo(msg).unsafe(self.vim)

    def echom(self, msg: str) -> None:
        echo(msg).unsafe(self.vim)


class NvimFilter(logging.Filter):

    def filter(self, record: logging.LogRecord) -> bool:
        return record.exc_info is None


nvim_filter = NvimFilter()
ribo_log = log = ribosome_root_logger = amino_logger('nvim')
_nvim_logging_initialized = False


def ribosome_logger(name: str) -> Logger:
    return ribosome_root_logger.getChild(name)


def ribosome_file_logging(name: str, file_kw: dict=dict()) -> logging.Handler:
    prefix_path = options.nvim_log_file.value | (lambda: amino.logging.log_dir() / 'nvim')
    level = (
        DDEBUG
        if options.development and options.spec else
        options.file_log_level.value | logging.DEBUG
    )
    logfile = Path(f'{prefix_path}_ribo_{name}_{log_stamp()}')
    kw = merge(
        file_kw,
        dict(level=level, logfile=logfile)
    )
    return amino_root_file_logging(**kw)


def ribosome_envvar_file_logging() -> None:
    fmt = options.file_log_fmt.value / (lambda fmt: dict(fmt=fmt)) | dict()
    options.ribo_log_file.value % (lambda f: amino_root_file_logging(logfile=Path(f), level=TEST, **fmt))


def ribosome_nvim_handler(vim: 'ribosome.NvimApi') -> None:
    handler = NvimHandler(vim)
    handler.addFilter(nvim_filter)
    ribosome_root_logger.addHandler(handler)
    init_loglevel(handler, VERBOSE)


def nvim_logging(vim: 'ribosome.NvimApi', file_kw: dict=dict()) -> logging.Handler:
    global _nvim_logging_initialized
    if not _nvim_logging_initialized:
        ribosome_nvim_handler(vim)
        _nvim_logging_initialized = True
        ribosome_envvar_file_logging()
        return ribosome_file_logging(vim.name, file_kw)


class Logging(amino.logging.Logging):

    @lazy
    def _log(self) -> Logger:
        return ribosome_logger(self.__class__.__name__)


def pr(a: A) -> A:
    v = log.verbose
    v(a)
    return a


def pv(a: A) -> A:
    v = log.verbose
    v(str(a))
    return a


def print_ribo_log_info(out: Callable[[str], None]) -> None:
    print_log_info(out)
    out(str(options.development))
    out(str(options.spec))
    out(str(options.file_log_level))
    out(str(options.file_log_fmt))
    out(str(options.nvim_log_file))

__all__ = ('ribosome_logger', 'nvim_logging', 'Logging', 'pr', 'ribo_log')
