rplugin_template = '''
import neovim
import os
import logging
from pathlib import Path

from {plugin_module} import {plugin_class}

import amino

amino.development = True

import amino.logging
from ribosome.logging import ribosome_root_logger

logfile = Path(os.environ['RIBOSOME_LOG_FILE'])
fmt = os.environ.get('RIBOSOME_FILE_LOG_FMT')
amino.logging.amino_file_logging(ribosome_root_logger,
                                 level=amino.logging.VERBOSE,
                                 logfile=logfile,
                                 fmt=fmt)


@neovim.plugin
class Plugin({plugin_class}):
    pass
'''

__all__ = ('rplugin_template',)
