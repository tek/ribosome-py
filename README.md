[![gitter](https://badges.gitter.im/tek/ribosome.svg)](https://gitter.im/tek/ribosome)

# Intro

**ribosome** is a framework for building and testing **neovim** python remote plugins.
It builds on the official [neovim-python] host, providing a more flexible and modular startup mechanism.

Plugins built with **ribosome** can be conveniently managed by [chromatin].

# Definition

*ribosome* plugins are defined declaratively.
Configuration is contained in a single instance of class `Config`, which is located by the plugin host by importing the
main module and analyzing the `__all__` attribute.
The minimal requirement is the plugin name:

```python
from ribosome.config import Config

config = Config(name='counter')

__all__ = ('config',)
```

# Starting

The recommended way to launch a *ribosome* plugin is to use [chromatin].

At runtime, a plugin can be added with:

```vim
Cram /path/to/package counter
```

To load the plugin automatically on start:

```vim
let g:chromatin_rplugins = [
  \ {
  \   'name': 'counter',
  \   'spec': '/path/to/package',
  \ }
  \ ]
```

The directory in `spec` has to be a package that *pip* can install, containing a `setup.py`.

To test a plugin without chromatin, it can be started manually:

```vim
call jobstart()
```

# Request Handlers


# Components and Messages


# Settings

# Documentation

[neovim-python]: https://github.com/neovim/python-client
[chromatin]: https://github.com/tek/chromatin
