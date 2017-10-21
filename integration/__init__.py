import subprocess
import os


def compile(path: str) -> None:
    subprocess.run(['coconut', '--target', '3.6', '--quiet', '--strict', path])


if 'COCO_DIRS' in os.environ:
    for dir in os.environ.get('COCO_DIRS', '').split(':'):
        compile(dir)

compile('myo')

import amino.test
amino.test.setup(__file__)
