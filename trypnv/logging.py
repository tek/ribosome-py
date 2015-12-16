import logging

from tryp.lazy import lazy
import tryp.logging
from tryp.logging import tryp_logger, tryp_root_logger, init_loglevel

from trypnv.nvim import NvimFacade


class NvimHandler(logging.Handler):

    def __init__(self, vim: NvimFacade) -> None:
        self.vim = vim
        self.dispatchers = {
            logging.INFO: self.vim.echo,
            logging.WARN: self.vim.echowarn,
            logging.ERROR: self.vim.echoerr,
            logging.CRITICAL: self.vim.echoerr,
        }
        super(NvimHandler, self).__init__()

    def emit(self, record: logging.LogRecord):
        dispatcher = self.dispatchers.get(record.levelno, self.vim.echom)
        dispatcher(record.getMessage())


log = trypnv_root_logger = tryp_logger('nvim')
_nvim_logging_initialized = False


def trypnv_logger(name: str):
    return trypnv_root_logger.getChild(name)


def nvim_logging(vim: NvimFacade, level: int=None):
    global _nvim_logging_initialized
    if not _nvim_logging_initialized:
        handler = NvimHandler(vim)
        trypnv_root_logger.addHandler(handler)
        handler.setLevel(logging.INFO)
        init_loglevel(tryp_root_logger)
        _nvim_logging_initialized = True


class Logging(tryp.logging.Logging):

    @lazy
    def _log(self) -> tryp.logging.Logger:
        return trypnv_logger(self.__class__.__name__)

__all__ = ['trypnv_logger', 'nvim_logging', 'Logging']
