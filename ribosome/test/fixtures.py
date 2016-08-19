rplugin_template = '''
import neovim
import os
import logging
from pathlib import Path

from {plugin_module} import {plugin_class}

import amino

amino.development = True

import amino.logging

logfile = Path(os.environ['RIBOSOME_LOG_FILE'])
amino.logging.amino_file_logging(level=logging.DEBUG,
                               handler_level=logging.DEBUG,
                               logfile=logfile)


@neovim.plugin
class Plugin({plugin_class}):
    pass
'''

__all__ = ('rplugin_template',)
