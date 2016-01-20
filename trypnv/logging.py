import logging

import tryp
from tryp.lazy import lazy
import tryp.logging
from tryp.logging import tryp_logger, init_loglevel


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


log = trypnv_root_logger = tryp_logger('nvim')
_nvim_logging_initialized = False


def trypnv_logger(name: str):
    return trypnv_root_logger.getChild(name)


def nvim_logging(vim, level: int=None, handler_level: int=logging.INFO):
    global _nvim_logging_initialized
    if not _nvim_logging_initialized:
        if level is None and not tryp.development:
            level = logging.INFO
        handler = NvimHandler(vim)
        trypnv_root_logger.addHandler(handler)
        handler.setLevel(handler_level)
        init_loglevel(trypnv_root_logger, level)
        _nvim_logging_initialized = True


class Logging(tryp.logging.Logging):

    @lazy
    def _log(self):
        return trypnv_logger(self.__class__.__name__)

__all__ = ('trypnv_logger', 'nvim_logging', 'Logging')
