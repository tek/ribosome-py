from setuptools import setup, find_packages

from trypnv.version import version

setup(
    name='tryp-nvim',
    description='neovim helpers',
    version=version,
    author='Torsten Schmits',
    author_email='torstenschmits@gmail.com',
    license='MIT',
    url='https://github.com/tek/tryp-nvim',
    packages=find_packages(exclude=['unit', 'unit.*']),
    install_requires=[
        'tryp>=6.4.0',
        'neovim',
        'pyrsistent',
    ]
)
