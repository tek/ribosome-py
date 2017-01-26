import os
import logging

from toolz import merge

import amino
from amino.lazy import lazy
import amino.logging
from amino.logging import (amino_logger, init_loglevel, amino_file_logging,
                           DDEBUG)
from amino import Path, env


class NvimHandler(logging.Handler):

    def __init__(self, vim):
        self.vim = vim
        self.dispatchers = {
            logging.INFO: self.vim.echo,
            logging.WARN: self.vim.echowarn,
            logging.ERROR: self.vim.echoerr,
            logging.CRITICAL: self.vim.echoerr,
        }
        super().__init__()

    def emit(self, record: logging.LogRecord):
        dispatcher = self.dispatchers.get(record.levelno, self.vim.echom)
        dispatcher(record.getMessage())


log = ribosome_root_logger = amino_logger('nvim')
_nvim_logging_initialized = False


def ribosome_logger(name: str):
    return ribosome_root_logger.getChild(name)


def nvim_logging(vim, level: int=logging.INFO, file_kw=dict()):
    global _nvim_logging_initialized
    if not _nvim_logging_initialized:
        if level is None and not amino.development:
            level = logging.INFO
        handler = NvimHandler(vim)
        ribosome_root_logger.addHandler(handler)
        init_loglevel(handler, level)
        def file_log(prefix):
            level = (
                DDEBUG
                if 'RIBOSOME_DEVELOPMENT' in env and
                'RIBOSOME_SPEC' in env else
                None
            )
            logfile = Path('{}_ribo_{}'.format(prefix, os.getpid()))
            fmt_kw = lambda fmt: dict(fmt=fmt)
            kw = merge(
                file_kw,
                dict(level=level, logfile=logfile),
                env['RIBOSOME_FILE_LOG_FMT'] / fmt_kw | dict()
            )
            amino_file_logging(ribosome_root_logger, **kw)
        amino.env['NVIM_PYTHON_LOG_FILE'] % file_log
        _nvim_logging_initialized = True


class Logging(amino.logging.Logging):

    @lazy
    def _log(self):
        return ribosome_logger(self.__class__.__name__)


def pr(a):
    v = log.verbose
    v(a)
    return a


def pv(a):
    v = log.verbose
    v(str(a))
    return a

__all__ = ('ribosome_logger', 'nvim_logging', 'Logging', 'pr')
