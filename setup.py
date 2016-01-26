from setuptools import setup, find_packages  # type: ignore

setup(
    name='tryp-nvim',
    description='neovim helpers',
    version='5.1.0',
    author='Torsten Schmits',
    author_email='torstenschmits@gmail.com',
    license='MIT',
    url='https://github.com/tek/tryp-nvim',
    packages=find_packages(exclude=['unit', 'unit.*']),
    install_requires=[
        'tryp>=5.0.0',
        'neovim',
        'pyrsistent',
    ]
)
