import logging

from tryp.lazy import lazy

import tryp
from tryp.logging import tryp_logger

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


def trypnv_logger(name: str):
    return trypnv_root_logger.getChild(name)


def nvim_logging(vim: NvimFacade):
    handler = NvimHandler(vim)
    trypnv_root_logger.addHandler(handler)
    if not tryp.development:
        handler.setLevel(logging.INFO)


class Logging(object):

    @property
    def log(self) -> logging.Logger:
        return self._log  # type: ignore

    @lazy
    def _log(self) -> logging.Logger:
        return trypnv_logger(self.__class__.__name__)

__all__ = ['trypnv_logger', 'nvim_logging']
