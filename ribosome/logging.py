import os
import logging
from typing import TypeVar, Callable

from toolz import merge

import amino
from amino.lazy import lazy
import amino.logging
from amino.logging import (amino_logger, init_loglevel, amino_root_file_logging, DDEBUG, print_log_info, VERBOSE,
                           LazyRecord, TEST)
from amino import Path, Logger

import ribosome  # noqa
from ribosome import options

A = TypeVar('A')


class NvimHandler(logging.Handler):

    def __init__(self, vim: 'ribosome.NvimFacade') -> None:
        self.vim = vim
        self.dispatchers = {
            logging.INFO: self.vim.echo,
            logging.WARN: self.vim.echowarn,
            logging.ERROR: self.vim.echoerr,
            logging.CRITICAL: self.vim.echoerr,
        }
        super().__init__()

    def emit(self, record: LazyRecord) -> None:
        dispatcher = self.dispatchers.get(record.levelno, self.vim.echom)
        dispatcher(record.short())


class NvimFilter(logging.Filter):

    def filter(self, record: logging.LogRecord) -> bool:
        return record.exc_info is None


nvim_filter = NvimFilter()
ribo_log = log = ribosome_root_logger = amino_logger('nvim')
_nvim_logging_initialized = False


def ribosome_logger(name: str) -> Logger:
    return ribosome_root_logger.getChild(name)


def ribosome_file_logging(name: str, file_kw: dict=dict()) -> None:
    prefix_path = options.nvim_log_file.value | (lambda: amino.logging.log_dir() / 'nvim')
    level = (
        DDEBUG
        if options.development and options.spec else
        options.file_log_level.value | logging.DEBUG
    )
    logfile = Path(f'{prefix_path}_ribo_{name}_{os.getpid()}')
    kw = merge(
        file_kw,
        dict(level=level, logfile=logfile)
    )
    return amino_root_file_logging(**kw)


def nvim_logging(vim: 'ribosome.NvimFacade', level: int=logging.INFO, file_kw: dict=dict()) -> logging.Handler:
    global _nvim_logging_initialized
    if not _nvim_logging_initialized:
        if level is None and not amino.development:
            level = logging.INFO
        handler = NvimHandler(vim)
        handler.addFilter(nvim_filter)
        ribosome_root_logger.addHandler(handler)
        init_loglevel(handler, VERBOSE)
        _nvim_logging_initialized = True
        fmt = options.file_log_fmt.value / (lambda fmt: dict(fmt=fmt)) | dict()
        options.ribo_log_file.value % (lambda f: amino_root_file_logging(logfile=Path(f), level=TEST, **fmt))
        return ribosome_file_logging(vim.prefix, file_kw)


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
