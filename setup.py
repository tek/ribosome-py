from setuptools import setup, find_packages

version_parts = (13, 0, 0, 'a', 48)
version = '.'.join(map(str, version_parts))

setup(
    name='ribosome',
    description='neovim plugin framework',
    version=version,
    author='Torsten Schmits',
    author_email='torstenschmits@gmail.com',
    license='MIT',
    url='https://github.com/tek/ribosome',
    packages=find_packages(exclude=['unit', 'unit.*', 'integration', 'integration.*', 'test', 'test.*']),
    install_requires=[
        'amino==13.0.0a24',
        'pyuv~=1.4.0',
        'mypy_extensions==0.3.0',
    ],
    tests_require=[
        'chiasma~=0.1.0.a20',
        'kallikrein~=0.22.0a15',
    ],
    entry_points={
        'console_scripts': [
            'ribosome_start_plugin = ribosome.cli:start_plugin',
        ],
    },
)
