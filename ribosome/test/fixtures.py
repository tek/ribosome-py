rplugin_template = '''
import neovim
import os
import sys
import logging
from pathlib import Path

import amino

amino.development = True

import amino.logging
from ribosome.logging import ribosome_root_logger

logfile = Path(os.environ['RIBOSOME_LOG_FILE'])
fmt = os.environ.get('RIBOSOME_FILE_LOG_FMT')
amino.logging.amino_root_file_logging(level=amino.logging.TEST, logfile=logfile, fmt=fmt)

pkg_dir = os.environ.get('RIBOSOME_PKG_DIR')
if pkg_dir:
    sys.path.insert(0, pkg_dir)

try:
    from {plugin_module} import {plugin_class}
except Exception as e:
    ribosome_root_logger.caught_exception('importing {plugin_module}.{plugin_class}', e)
    raise

@neovim.plugin
class SpecPlugin({plugin_class}, debug=True):
    pass

__all__ = ('SpecPlugin',)
'''

__all__ = ('rplugin_template',)
