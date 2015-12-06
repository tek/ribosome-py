from tek import logger  # type: ignore


class VimLog(object):

    def __init__(self, vim):
        self.vim = vim

    def info(self, msg: str):
        self.vim.echo(msg)

    def warn(self, msg: str):
        self.vim.echowarn(msg)

    def error(self, msg: str):
        self.vim.echoerr(msg)

    def debug(self, msg):
        pass


class DebugLog(object):

    def info(self, msg: str):
        logger.info(msg)

    def warn(self, msg: str):
        logger.warn(msg)

    def error(self, msg: str):
        logger.error(msg)

    def debug(self, msg: str):
        logger.debug(msg)


__all__ = ['VimLog', 'DebugLog']
