rplugin_template = '''
import neovim
import os
import logging
from pathlib import Path

from {plugin_module} import {plugin_class}

import tryp

tryp.development = True

import tryp.logging

logfile = Path(os.environ['TRYPNV_LOG_FILE'])
tryp.logging.tryp_file_logging(level=logging.DEBUG,
                               handler_level=logging.DEBUG,
                               logfile=logfile)


@neovim.plugin
class Plugin({plugin_class}):
    pass
'''

__all__ = ('rplugin_template',)
