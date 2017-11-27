from setuptools import setup, find_packages

version_parts = (13, 0, 0, 'a', 1)
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
        'amino~=12.5.0',
        'neovim~=0.1.13',
        'pyrsistent~=0.12.3',
        'pyuv~=1.4.0',
    ],
    tests_require=[
        'libtmux~=0.7.4',
        'kallikrein~=0.21.0',
    ],
    entry_points={
        'console_scripts': [
            'ribosome_start_plugin = ribosome.cli:start_plugin',
        ],
    },
)
