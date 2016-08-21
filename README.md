# Intro
A framework for building and testing neovim-python plugins consisting of:
* convenient decorators for commands with json argument parsing
* message-passing machines for command dispatching
* neovim API abstractions
* integraton test framework
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
[proteome.nvim] plugin.

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

# API Facade

# Testing

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

For in-depth examples, consider the specs in [proteome].

# Neovim Runtime
The [giter8] template creates a directory named `runtime` in the project root,
you can link or copy it to your bundle dir and execute `:UpdateRemotePlugins`.

[amino]: https://github.com/tek/amino
[proteome.nvim]: https://github.com/tek/proteome.nvim
[proteome]: https://github.com/tek/proteome
[pyrsistent]: https://github.com/tobgu/pyrsistent
[spec]: https://github.com/bitprophet/spec
[giter8]: https://github.com/foundweekends/giter8
