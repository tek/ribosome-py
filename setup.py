from setuptools import setup, find_packages

version_parts = (7, 4, 1)
version = '.'.join(map(str, version_parts))

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
        'tryp>=7.3.0',
        'neovim',
        'pyrsistent',
    ]
)
