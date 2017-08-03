import os
import logging
from typing import TypeVar

from toolz import merge

import amino
from amino.lazy import lazy
import amino.logging
from amino.logging import amino_logger, init_loglevel, amino_root_file_logging, DDEBUG, amino_root_logger
from amino import Path, env

import ribosome  # noqa

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

    def emit(self, record: logging.LogRecord) -> None:
        dispatcher = self.dispatchers.get(record.levelno, self.vim.echom)
        dispatcher(record.getMessage())


class NvimFilter(logging.Filter):

    def filter(self, record: logging.LogRecord) -> bool:
        return record.exc_info is None

nvim_filter = NvimFilter()
ribo_log = log = ribosome_root_logger = amino_logger('nvim')
_nvim_logging_initialized = False


def ribosome_logger(name: str) -> logging.Logger:
    return ribosome_root_logger.getChild(name)


def nvim_logging(vim: 'ribosome.NvimFacade', level: int=logging.INFO, file_kw: dict=dict()) -> None:
    global _nvim_logging_initialized
    if not _nvim_logging_initialized:
        if level is None and not amino.development:
            level = logging.INFO
        handler = NvimHandler(vim)
        handler.addFilter(nvim_filter)
        ribosome_root_logger.addHandler(handler)
        init_loglevel(handler, level)
        def file_log(prefix: str) -> None:
            level = (
                DDEBUG
                if 'RIBOSOME_DEVELOPMENT' in env and 'RIBOSOME_SPEC' in env else
                env['RIBOSOME_FILE_LOG_LEVEL'] | logging.INFO
            )
            logfile = Path('{}_ribo_{}'.format(prefix, os.getpid()))
            fmt = env['RIBOSOME_FILE_LOG_FMT'] / (lambda fmt: dict(fmt=fmt)) | dict()
            kw = merge(
                file_kw,
                dict(level=level, logfile=logfile),
                fmt
            )
            amino_root_file_logging(**kw)
        amino.env['NVIM_PYTHON_LOG_FILE'] % file_log
        _nvim_logging_initialized = True


class Logging(amino.logging.Logging):

    @lazy
    def _log(self) -> logging.Logger:
        return ribosome_logger(self.__class__.__name__)


def pr(a: A) -> A:
    v = log.verbose
    v(a)
    return a


def pv(a: A) -> A:
    v = log.verbose
    v(str(a))
    return a

__all__ = ('ribosome_logger', 'nvim_logging', 'Logging', 'pr', 'ribo_log')
