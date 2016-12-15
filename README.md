[![Join the chat at https://gitter.im/tek/ribosome](https://badges.gitter.im/tek/ribosome.svg)](https://gitter.im/tek/ribosome?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

# Intro
A framework for building and testing [neovim-python] plugins consisting of:
* convenient decorators for commands and functions with json argument parsing
* message-passing machines for command dispatching
* neovim API abstractions
* integration test framework
* pure and functional principles

# Use

The pypi name is *ribosome*.

To get started with a fully functional skeleton project, use [giter8]:

```
g8 tek/ribosome
cd <projectdir>
pip install -r requirements.txt
spec integration
```

The last command runs the dummy test to verify it works.

*ribosome* heavily uses functional data structures from [amino] and
[pyrsistent].

As a comprehensive example for how to use this framework, take a look at the
[proteome] plugin ([doc][proteome.nvim]).

# Basic
The class `ribosome.NvimPlugin` serves as an optional base class that handles
setup of the [NvimFacade](#api-facade) instance, comfortable logging and some
`asyncio` necessities.

```python
class XPlugin(ribosome.NvimPlugin):

    def __init__(self, vim: neovim.Nvim) -> None:
        super().__init__(vim)
        self.x = None

    @property
    def name(self):
        return 'example'
```

# Commands

### Simple

The `ribosome.command` decorator works like the one from `neovim-python`,
but uses the name of the decorated function, converted to CamelCase, for the
command name and the function parameters as command parameters.

```python
class XPlugin(ribosome.NvimPlugin):

    @ribosome.command(sync=True)
    def x_start(self, init='1'):
        if init == '1':
            self.x = X(self.vim)
            self.x.start()
```

This creates a sync command named `XStart` that takes one optional argument
(`-nargs=?`).
The object `x` is the [state machine](#machines) used below.
This decorator can be used independently of the base class and all other
features.

### Message Command

The `ribosome.msg_command` decorator takes a type as positional argument
and does not execute the method, but rather sends an instance of the given
type to the [state machine](#machines), carrying the supplied arguments.

### JSON Message Command

The `ribosome.json_msg_command` decorator assumes the non-positional
arguments to be literal json or python, which is parsed and passed to the
message constructor.

# Functions

The `ribosome.function` decorator works identically to the command decorator,
but defaulting to `sync=True`.

# Machines

**ribosome** contains a framework for message-passing machines defined by a set
of transition methods for handling state transformation in a pure way.

A plugin can have an arbitrary number of nested machines that run on a single
asyncio event loop.

The root machine can be created by subclassing `ribosome.StateMachine`, which
encapsulates a state object of your custom type.
`ribosome.PluginStateMachine` allows nesting additional machines as
configurable plugins.
`ribosome.RootMachine` is a subclass of `PluginStateMachine` with some extras:
logging and vim access.

```python
class XState(ribosome.Data):
    counter = ribosome.record.dfield(0)

class X(ribosome.RootMachine):

    def init(self):
        return XState(0)
```

The `XState` class inherits `ribosome.Data`, which in turn subclasses
[`pyrsistent.PRecord`][pyrsistent], an immutable data structure.
The counter field uses `pyrsistent.field` internally.

Its method `StateMachine.send(msg: Message)` looks for a matching transition
method and calls it with the current state and `msg`, updating the state with
the (optional) result of the call.

A transition can be defined using one of several decorators.

```python
Increment = message('Increment', 'amount')
Print = message('Print')

class X(ribosome.RootMachine):

    def __init__(self):
        super().__init__(amino.List('x.plugins.config'))

    @ribosome.may_handle(Increment)
    def increment(self, data: XState, msg: Increment):
        new_data = data.set(counter=data.counter + msg.amount)
        return new_data, Print()

    @ribosome.handle(Print)
    def print_counter(self, data: XState, msg: Print):
        self.log.info('current count: {}'.format(data.counter))
        return amino.Empty()
```

The `message` helper creates a subclass of `Message` with low boilerplate.
For json commands, the `json_message` function must be used, which adds an
additional dict field called `options`.

The decorators take as argument the class of the message which they can handle.
In the example, the counter is incremented by the amount specified in the
message and returned, along with a new message.

Transition functions can return either a transformed state instance, one or
more messages or both.

If one of the results is of the state type, it will replace the old state for
future transitions; all returned messages will be resent.

The difference between the decorators `handle` and `may_handle` is that the
former expects the transition result to be wrapped inside an instance of
`amino.Maybe`, which can either be `Just(value)` or `Empty()`, signifying
whether something happened or not; with `may_handle`, the returned value can
either be the plain version of the transition result or `None` (i.e. no return
statement at all).

Message handlers can have a priority value that can be used to select one
handler over another, even across different machines.
If one or more handlers of a higher priority are available, only they are used.
The priority can be specified via keyword argument, as in
`@handle(Print, prio=0.9)`.
The default priority is `0.5`, and there are two extra decorators available:
* `@override(Print) with prio=0.8`
* `@fallback(Print) with prio=0.3`
That way, it is possible for custom plugins to block transitions in standard
plugins.

`self.log` is part of the `ribosome.Logging` class which sets up logging to
file and *neovim*, using the latter's `echo` (for `log.info`) and `echohl` (for
`log.warn` and `log.error`) commands.

To explicitly send a message to the root machine from your plugin class, use
the send method:

```python
self.x.send(Increment(5))
```

## Commands

To easily connect a *neovim* command to a machine transition, use the
`msg_command` decorator:

```python
class XPlugin(ribosome.NvimPlugin):
    ...

    @property
    def state(self):
        return self.x

    @ribosome.msg_command(x.Increment)
    def x_increment(self):
        pass
```

The decorator analyzes the `Increment` message's constructor and accordingly
configures the *neovim* command, here creating a one-argument async command
named `XIncrement`.

## Submachines

`PluginStateMachine` can easily host nested machines that each handle messages.
This can be facilitated by passing a list of module names to
`PluginStateMachine.__init__`.
Int the above example, the module `x.plugins.config` is imported; if it
contains a class named `Plugin`, it will be instantiated and used as a child
machine.

If the root machine encounters a message for which it has no own transition
handler, the submachines are queried in order and each can perform a
transition.

To allow plugins to send messages to others, the messages must be published, by
accessing the `pub` attribute, as in
```python
return Increment(2).pub
```

## Modular Transitions

To avoid having to pass the state and message arguments along with helper
functions, a more comfortable variant of transition definition is possible by
extending `ribosome.ModularMachine`.
With this class, each message is handled by a fresh instance of the nested
class `Transitions`, which is initialized with the current state and message as
instances attributes:

```python
Reset = message('Reset', 'value')

class XSubTransitions(ribosome.Transitions):

    @ribosome.may_handle(Increment)
    def increment(self):
        new_data = self.data.set(counter=self.msg.value)
        return new_data, Print().pub

class Plugin(ribosome.ModularMachine):
  Transitions = XSubTransitions
```

Here, the `.pub` transformation must be used in order to reach the parent
machine where the `Print` message is handled.

# API Facade

The class `NvimFacade` provides an entry point into more abstract and
comfortable Nvim API functionality.

### async

One of the most significant features is the seamless dispatching of rpc
requests from concurrent and asyncio contexts by executing all methods on the
*neovim-python* main loop.

### typed and functional data

Numerous convenient adapters for retrieving and setting options and variables
provide safer interaction with *neovim*.

All getters return a monadic `amino.Maybe` which is `Just(value)` if the
data was found and is of valid type, and `Empty()` otherwise.

```python
self.vim.options('filetype') # => Just('python')
self.vim.vars('garbage') # => Empty()
self.vim.options.l('rtp') # => Just(List('~/.config/nvim/bundle/proteome.nvim'))
```

For shorter variable names, `NvimFacade` is initialized with a prefix (the
plugin name by default, here: `proteome`).
All getters have an alternative variant starting with `p` that uses the prefix
for the variable name:

```python
self.vim.vars.pl('projects') # => Just(List('proteome', 'ribosome', 'amino'))
```
This queries the variable `g:proteome_projects`, converts it to
`amino.List` and wraps it in `amino.Maybe`.

Check out the source code to discover command execution, autocmds, boolean
flags, the tab/window/buffer hierarchy and more.
Hopefully, there will be better API doc soon.

# Testing

### Complete Integration

*ribosome* provides a convenient way of integration testing your plugin within
a running *neovim* instance using the [spec] plugin for *nose*.

```python
class IntegrationSpec(ribosome.test.PluginIntegrationSpec):

    @property
    def plugin_class(self):
        return amino.Right(x.XPlugin)

class IncrementSpec(IntegrationSpec):

    def inc(self):
        self.vim.cmd_sync('XStart')
        self.vim.cmd('XIncrement 8')
        ...
```

The base class runs an embedded *neovim* instance, creates a subclass of
`XPlugin` with the `@neovim.plugin` decorator and registers all of its
request handlers.

Set `self._debug = True` to print all logged messages to stdout at the end of
the test run.

Set `self.tmux_nvim = True` or the env var `$RIBOSOME_TMUX_SPEC` to run the
instance in a split pane instead of a child process.

For in-depth examples, consider the specs in [proteome].

### Semi-Integration

There is also a *light* variant of integration test which also uses a *neovim*
child process but starts the plugin in the main process, making it simpler to
interact with it.

The equivalent version of the above spec is:

```python
class IncrementSpec(ribosome.test.ExternalIntegrationSpec):

    @property
    def plugin_class(self):
        return amino.Right(x.XPlugin)

    def inc(self):
        self.state.x_start()
        self.root.send(Increment(8))
        ...
```

Here `self.state` is the `XPlugin` instance and `self.root` is the `X`
instance.

# Neovim Runtime
If you want to publish your plugin as a python egg with a minimal adapter
*neovim* plugin, the [giter8] template creates a directory named `runtime` in
the project root, you can link or copy it to your bundle dir and execute
`:UpdateRemotePlugins` for testing or publish it as a plugin.

[neovim-python]: https://github.com/neovim/python-client
[amino]: https://github.com/tek/amino
[proteome.nvim]: https://github.com/tek/proteome.nvim
[proteome]: https://github.com/tek/proteome
[pyrsistent]: https://github.com/tobgu/pyrsistent
[spec]: https://github.com/bitprophet/spec
[giter8]: https://github.com/foundweekends/giter8
