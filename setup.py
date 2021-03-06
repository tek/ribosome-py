from setuptools import setup, find_packages

version_parts = (13, 0, 2, 'a', 8)
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
        'amino~=13.0.1a9',
        'msgpack-python~=0.5.6'
    ],
    tests_require=[
        'chiasma~=0.1.0.a28',
        'kallikrein~=0.22.0a15',
    ],
    entry_points={
        'console_scripts': [
            'ribosome_start_plugin = ribosome.cli:start_plugin',
        ],
    },
)
