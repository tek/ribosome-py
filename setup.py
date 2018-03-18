from setuptools import setup, find_packages

version_parts = (13, 0, 0, 'a', 22)
version = '.'.join(map(str, version_parts))

setup(
    name='ribosome',
    description='neovim plugin framework',
    version=version,
    author='Torsten Schmits',
    author_email='torstenschmits@gmail.com',
    license='MIT',
    url='https://github.com/tek/ribosome',
    packages=find_packages(exclude=['unit', 'unit.*']),
    install_requires=[
        'amino==13.0.0a14',
        'neovim~=0.1.13',
        'pyuv~=1.4.0',
    ],
    tests_require=[
        'libtmux~=0.7.4',
        'kallikrein~=0.22.0a',
    ],
    entry_points={
        'console_scripts': [
            'ribosome_start_plugin = ribosome.cli:start_plugin',
        ],
    },
)
