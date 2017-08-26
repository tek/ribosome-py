from setuptools import setup, find_packages

version_parts = (10, 12, 0)
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
        'amino==10.8.2',
        'neovim==0.1.13',
        'pyrsistent==0.12.3',
    ]
)
