import abc
import inspect
from types import FunctionType
from typing import TypeVar, Callable, Union, Any, Dict, Generator

from amino import Map, Maybe, Lists, List, Either, Just, Nothing, do, Boolean, _, L, __, Do
from amino.util.string import camelcaseify, ToStr
from amino.list import Nil
from amino.dat import Dat

from ribosome.nvim import NvimFacade, NvimIO
from ribosome.logging import ribo_log

A = TypeVar('A')


def rpc_cmd_opt(key: str, value: Union[str, int]) -> Maybe[str]:
    return (
        Just(f'-nargs={value}')
        if key == 'nargs' else
        Just('-bang')
        if key == 'bang' else
        Nothing
    )


def rpc_cmd_arg(key: str, value: Union[str, int]) -> Maybe[str]:
    return (
        Just(f'[<f-args>]')
        if key == 'nargs' else
        Just('<q-bang> == "!"')
        if key == 'bang' else
        Nothing
    )


def rpc_autocmd_opt(key: str, value: Union[str, int]) -> Maybe[str]:
    return (
        Just(str(value))
        if key == 'pattern' else
        Nothing
    )


RHS = TypeVar('RHS', bound='RpcHandlerSpec')


def from_bool(a: Union[int, bool, Boolean]) -> int:
    return a.to_int if isinstance(a, Boolean) else int(a) if isinstance(a, bool) else a


class RpcHandlerSpec(Dat['RpcHandlerSpec']):

    @staticmethod
    def cons(Ctor: type,
             sync: Union[int, bool, Boolean],
             name: str,
             opts: dict,
             method: str,
             prefix: bool) -> 'RpcHandlerSpec':
        return Ctor(from_bool(sync), name, opts, method, Boolean(prefix))

    @staticmethod
    @do(Maybe['RpcHandlerSpec'])
    def from_spec(spec: Dict[str, Any], method: str, prefix: bool) -> Do:
        m = Map(spec)
        ctors = Map(command=RpcCommandSpec, function=RpcFunctionSpec, autocmd=RpcAutocommandSpec)
        tpe = yield m.lift('type')
        Ctor = yield ctors.lift(tpe)
        sync, name, opts = yield m.get_all('sync', 'name', 'opts')
        yield Just(RpcHandlerSpec.cons(Ctor, sync, name, opts, method, prefix))

    @staticmethod
    def cmd(sync: int, name: str, opts: dict) -> 'RpcHandlerSpec':
        method = f'command:{name}'
        return RpcHandlerSpec.cons(RpcCommandSpec, sync, name, opts, method, True)

    @staticmethod
    def fun(sync: int, name: str, opts: dict) -> 'RpcHandlerSpec':
        method = f'function:{name}'
        return RpcHandlerSpec.cons(RpcFunctionSpec, sync, name, opts, method, True)

    @staticmethod
    def autocmd(sync: int, name: str, opts: dict) -> 'RpcHandlerSpec':
        method = f'autocmd:{name}'
        return RpcHandlerSpec.cons(RpcAutocommandSpec, sync, name, opts, method, True)

    @staticmethod
    @do('Maybe[RpcHandlerSpec]')
    def decode(data: dict) -> Do:
        m = Map(data)
        method, prefix = yield m.get_all('method', 'prefix')
        yield RpcHandlerSpec.from_spec(m, method, prefix)

    @abc.abstractproperty
    def tpe(self) -> str:
        ...

    @abc.abstractproperty
    def rpc_opts_pre(self) -> List[str]:
        ...

    @abc.abstractproperty
    def rpc_opts_post(self) -> List[str]:
        ...

    @abc.abstractproperty
    def rpc_args(self) -> List[str]:
        ...

    @abc.abstractproperty
    def def_cmd(self) -> str:
        ...

    @abc.abstractproperty
    def undef_cmdline(self) -> str:
        ...

    def __init__(self, sync: Boolean, name: str, opts: dict, method: str, prefix: Boolean) -> None:
        self.sync = sync
        self.name = name
        self.opts = opts
        self.method = method
        self.prefix = prefix

    def _arg_desc(self) -> List[str]:
        return List(self.name, self.tpe, str(self.sync), str(self.opts), self.method, str(self.prefix))

    @property
    def rpc_function(self) -> str:
        return 'rpcrequest' if self.sync else 'rpcnotify'

    @property
    def rpc_method(self) -> str:
        return self.method

    @property
    def encode(self) -> dict:
        return dict(
            type=self.tpe,
            sync=self.sync,
            name=self.name,
            opts=self.opts,
            method=self.method,
            prefix=int(self.prefix.value),
        )


class RpcCommandArgs:

    def __init__(self, data: Map) -> None:
        self.data = data

    @property
    def tokens(self) -> List[str]:
        return self.nargs + self.bang

    @property
    def nargs(self) -> List[str]:
        return self.arg('nargs', lambda a: List('[<f-args>]'))

    @property
    def bang(self) -> List[str]:
        return self.arg('bang', lambda a: List("<q-bang> == '!'"))

    def arg(self, name: str, result: Callable[[str], List[str]]) -> List[str]:
        return self.data.lift(name) / result | Nil


class RpcCommandSpec(RpcHandlerSpec):

    @property
    def tpe(self) -> str:
        return 'command'

    @property
    def rpc_opts_pre(self) -> List[str]:
        return Map(self.opts).map2(rpc_cmd_opt).join

    @property
    def rpc_opts_post(self) -> List[str]:
        return Nil

    @property
    def rpc_args(self) -> List[str]:
        help = RpcCommandArgs(Map(self.opts))
        return help.tokens

    @property
    def def_cmd(self) -> str:
        return 'command!'

    @property
    def undef_cmdline(self) -> str:
        return f'delcommand {self.name}'


class RpcFunctionSpec(RpcHandlerSpec):

    @property
    def tpe(self) -> str:
        return 'function'

    @property
    def rpc_opts_pre(self) -> List[str]:
        return Nil

    @property
    def rpc_opts_post(self) -> List[str]:
        return Nil

    @property
    def rpc_args(self) -> List[str]:
        return List('a:000')

    @property
    def def_cmd(self) -> str:
        return 'function!'

    @property
    def undef_cmdline(self) -> str:
        return f'delfunction {self.name}'


class RpcAutocommandSpec(RpcHandlerSpec):

    @property
    def tpe(self) -> str:
        return 'autocmd'

    @property
    def rpc_opts_pre(self) -> List[str]:
        return List()

    @property
    def rpc_opts_post(self) -> List[str]:
        defaults = Map(pattern='*')
        return Map(defaults ** self.opts).map2(rpc_autocmd_opt).join

    @property
    def rpc_args(self) -> List[str]:
        return Nil

    @property
    def def_cmd(self) -> str:
        return 'autocmd'

    @property
    def undef_cmdline(self) -> str:
        return f'autocmd! {self.name}'


def handler(method_name: str, fun: FunctionType) -> Maybe[RpcHandlerSpec]:
    def get(name: str) -> Maybe[A]:
        return Maybe.getattr(fun, name)
    return (
        List('_nvim_rpc_spec', '_nvim_rpc_method_name', '_nvim_prefix_plugin_path')
        .traverse(get, Maybe)
        .flat_map3(RpcHandlerSpec.from_spec)
    )


class RpcHandlerFunction(ToStr):

    def __init__(self, func: Callable, spec: RpcHandlerSpec) -> None:
        self.func = func
        self.spec = spec

    def _arg_desc(self) -> List[str]:
        return List(str(self.spec))


def handler_function(method_name: str, fun: FunctionType) -> Maybe[RpcHandlerFunction]:
    return handler(method_name, fun) / L(RpcHandlerFunction)(fun, _)


def handler_function1(method_name: str, fun: FunctionType, name: str, prefix: str) -> Maybe[RpcHandlerFunction]:
    return Maybe.getattr(fun, 'spec') / __.spec(name, prefix) / L(RpcHandlerFunction)(fun, _)


def register_handler_args(host: str, spec: RpcHandlerSpec) -> List[str]:
    fun_prefix = camelcaseify(spec.tpe)
    return List(f'remote#define#{fun_prefix}OnHost', host, spec.rpc_method, spec.sync, spec.name, spec.opts)


def define_handler_native(vim: NvimFacade, host: str, spec: RpcHandlerSpec
                          ) -> Either[Exception, None]:
    ribo_log.debug1(lambda: f'defining {spec} on {host}')
    args = register_handler_args(host, spec)
    return vim.call(*args)


class DefinedHandler(Dat['DefinedHandler']):

    def __init__(self, spec: RpcHandlerSpec, channel: int) -> None:
        self.spec = spec
        self.channel = channel


def quote(a: str) -> str:
    return f"'{a}'"


def define_handler_cmd(rhs_f: Callable[[str], str], channel: int, spec: RpcHandlerSpec) -> List[str]:
    ribo_log.debug1(lambda: f'defining {spec} on channel {channel}')
    fun = spec.rpc_function
    args = spec.rpc_args.cons(quote(spec.rpc_method)).join_comma
    rpc_call = f'{fun}({channel}, {args})'
    rhs = rhs_f(rpc_call)
    return List(spec.def_cmd) + spec.rpc_opts_pre + List(spec.name) + spec.rpc_opts_post + List(rhs)


def define_handler_io(rhs: Callable[[str], str], channel: int, spec: RpcHandlerSpec
                      ) -> NvimIO[DefinedHandler]:
    tokens = define_handler_cmd(rhs, channel, spec)
    return NvimIO.cmd_sync(tokens.join_tokens).replace(DefinedHandler(spec, channel))


def define_function(channel: int, spec: RpcHandlerSpec) -> NvimIO[DefinedHandler]:
    return define_handler_io(lambda call: f'(...)\nreturn {call}\nendfunction', channel, spec)


def define_command(channel: int, spec: RpcHandlerSpec) -> NvimIO[DefinedHandler]:
    return define_handler_io(lambda a: f'call {a}', channel, spec)


@do(NvimIO[DefinedHandler])
def define_autocmd(channel: int, spec: RpcHandlerSpec, plugin_name: str) -> Generator:
    yield NvimIO.cmd_sync(f'augroup {plugin_name}')
    result = yield define_handler_io(lambda a: f'call {a}', channel, spec)
    yield NvimIO.cmd_sync(f'augroup end')
    yield NvimIO.pure(result)


def define_handler(channel: int, spec: RpcHandlerSpec, plugin_name: str) -> NvimIO[DefinedHandler]:
    if spec.tpe == 'function':
        return define_function(channel, spec)
    elif spec.tpe == 'command':
        return define_command(channel, spec)
    elif spec.tpe == 'autocmd':
        return define_autocmd(channel, spec, plugin_name)
    else:
        return NvimIO.failed(f'invalid type for {spec}')


@do(NvimIO[List[DefinedHandler]])
def define_handlers(specs: List[RpcHandlerSpec], plugin_name: str) -> Generator:
    channel = yield NvimIO.delay(_.channel_id)
    yield specs.traverse(L(define_handler)(channel, _, plugin_name), NvimIO)


def rpc_handlers(plugin_class: type) -> List[RpcHandlerSpec]:
    return Lists.wrap(inspect.getmembers(plugin_class)).flat_map2(handler)


def rpc_handlers_json(plugin_class: type) -> List[str]:
        return list(rpc_handlers(plugin_class) / _.encode)


def rpc_handler_functions(plugin: Any) -> List[RpcHandlerFunction]:
    funs = inspect.getmembers(plugin)
    return (
        Lists.wrap(funs).flat_map2(handler_function) +
        Lists.wrap(funs).flat_map2(L(handler_function1)(_, _, plugin.name, plugin.prefix))
    )

__all__ = ('RpcHandlerSpec', 'handler', 'define_handler', 'define_handlers', 'rpc_handlers', 'rpc_handlers_json',
           'rpc_handler_functions')
