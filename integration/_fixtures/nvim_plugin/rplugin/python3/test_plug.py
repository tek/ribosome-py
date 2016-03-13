import os
import logging
from pathlib import Path

import neovim

import tryp

tryp.development = True

import tryp.logging

from integration._support.plugin import TestPlugin

logfile = Path(os.environ['TRYPNV_LOG_FILE'])
tryp.logging.tryp_file_logging(level=logging.DEBUG,
                               handler_level=logging.DEBUG,
                               logfile=logfile)


@neovim.plugin
class Plugin(TestPlugin):
    pass
