import abc
import inspect
from types import FunctionType
from typing import TypeVar, Callable, Union, Any, Dict

from amino import Map, Maybe, Lists, List, Either, Just, Nothing, do
from amino.util.string import camelcaseify, ToStr
from amino.list import Nil

from ribosome.nvim import NvimFacade, NvimIO
from ribosome.logging import ribo_log

A = TypeVar('A')


def rpc_cmd_opt(key: str, value: Union[str, int]) -> Maybe[str]:
    return (
        Just(f'-nargs={value}')
        if key == 'nargs' else
        Nothing
    )


def rpc_cmd_arg(key: str, value: Union[str, int]) -> Maybe[str]:
    return (
        Just(f'[<f-args>]')
        if key == 'nargs' else
        Nothing
    )


def rpc_autocmd_opt(key: str, value: Union[str, int]) -> Maybe[str]:
    return (
        Just(str(value))
        if key == 'pattern' else
        Nothing
    )


RHS = TypeVar('RHS', bound='RpcHandlerSpec')


class RpcHandlerSpec(ToStr):

    @staticmethod
    @do
    def from_spec(spec: Dict[str, Any], method: str, prefix: bool) -> Maybe['RpcHandlerSpec']:
        m = Map(spec)
        ctors = Map(command=RpcCommandSpec, function=RpcFunctionSpec, autocmd=RpcAutocommandSpec)
        tpe = yield m.lift('type')
        Ctor = yield ctors.lift(tpe)
        sync, name, opts = yield m.get_all('sync', 'name', 'opts')
        yield Just(Ctor(sync, name, opts, method, prefix))

    @staticmethod
    def cmd(sync: int, name: str, opts: dict) -> 'RpcHandlerSpec':
        method = f'command:{name}'
        return RpcCommandSpec(sync, name, opts, method, True)

    @staticmethod
    def fun(sync: int, name: str, opts: dict) -> 'RpcHandlerSpec':
        method = f'function:{name}'
        return RpcFunctionSpec(sync, name, opts, method, True)

    @staticmethod
    @do
    def decode(data: dict) -> 'Maybe[RpcHandlerSpec]':
        m = Map(data)
        method, prefix = yield m.get_all('method', 'prefix')
        yield RpcHandlerSpec.from_spec(m, method, prefix)

    def __init__(self, sync: int, name: str, opts: dict, method: str, prefix: bool) -> None:
        self.sync = int(sync) if isinstance(sync, bool) else sync
        self.name = name
        self.opts = opts
        self.method = method
        self.prefix = prefix

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

    def _arg_desc(self) -> List[str]:
        return List(self.name, self.tpe, str(self.sync), str(self.opts), self.method, str(self.prefix))

    @property
    def rpc_function(self) -> str:
        return 'rpcrequest' if self.sync else 'rpcnotify'

    def rpc_method(self, plugin_file: str) -> str:
        pre = f'{plugin_file}:' if self.prefix else ''
        return f'{pre}{self.method}'

    @property
    def encode(self) -> dict:
        return dict(
            type=self.tpe,
            sync=self.sync,
            name=self.name,
            opts=self.opts,
            method=self.method,
            prefix=int(self.prefix),
        )


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
        return Map(self.opts).map2(rpc_cmd_arg).join

    @property
    def def_cmd(self) -> str:
        return 'command!'


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
        return Nil

    @property
    def def_cmd(self) -> str:
        return 'function!'


class RpcAutocommandSpec(RpcHandlerSpec):

    @property
    def tpe(self) -> str:
        return 'autocmd'

    @property
    def rpc_opts_pre(self) -> List[str]:
        return List()

    @property
    def rpc_opts_post(self) -> List[str]:
        return Map(self.opts).map2(rpc_autocmd_opt).join

    @property
    def rpc_args(self) -> List[str]:
        return Nil

    @property
    def def_cmd(self) -> str:
        return 'autocmd'


def handler(method_name: str, fun: FunctionType) -> Maybe[RpcHandlerSpec]:
    def get(name: str) -> Maybe[A]:
        return Maybe.getattr(fun, name)
    return (
        List('_nvim_rpc_spec', '_nvim_rpc_method_name', '_nvim_prefix_plugin_path')
        .traverse(get, Maybe)
        .flat_map3(RpcHandlerSpec.from_spec)
    )


def register_handler_args(host: str, spec: RpcHandlerSpec, plugin_file: str) -> List[str]:
    fun_prefix = camelcaseify(spec.tpe)
    return List(f'remote#define#{fun_prefix}OnHost', host, spec.rpc_method, spec.sync, spec.name, spec.opts)


def define_handler_native(vim: NvimFacade, host: str, spec: RpcHandlerSpec, plugin_file: str
                          ) -> Either[Exception, None]:
    ribo_log.debug1(lambda: f'defining {spec} on {host}')
    args = register_handler_args(host, spec, plugin_file)
    return vim.call(*args)


class DefinedHandler(ToStr):

    def __init__(self, spec: RpcHandlerSpec, channel: int) -> None:
        self.spec = spec
        self.channel = channel

    def _arg_desc(self) -> List[str]:
        return List(str(self.spec), str(self.channel))


def quote(a: str) -> str:
    return f"'{a}'"


def define_handler_cmd(rhs_f: Callable[[str], str], channel: int, spec: RpcHandlerSpec, plugin_file: str) -> List[str]:
    ribo_log.debug1(lambda: f'defining {spec} on channel {channel}')
    fun = spec.rpc_function
    method = spec.rpc_method(plugin_file)
    args = spec.rpc_args.cons(quote(method)).join_comma
    rpc_call = f'{fun}({channel}, {args})'
    rhs = rhs_f(rpc_call)
    return List(spec.def_cmd) + spec.rpc_opts_pre + List(spec.name) + spec.rpc_opts_post + List(rhs)


def define_handler_io(rhs: Callable[[str], str], channel: int, spec: RpcHandlerSpec, plugin_file: str
                      ) -> NvimIO[DefinedHandler]:
    tokens = define_handler_cmd(rhs, channel, spec, plugin_file)
    return NvimIO.cmd_sync(tokens.join_tokens).replace(DefinedHandler(spec, channel))


def define_function(channel: int, spec: RpcHandlerSpec, plugin_file: str) -> NvimIO[DefinedHandler]:
    return define_handler_io(lambda call: f'(...)\nreturn {call}\nendfunction', channel, spec, plugin_file)


def define_command(channel: int, spec: RpcHandlerSpec, plugin_file: str) -> NvimIO[DefinedHandler]:
    return define_handler_io(lambda a: f'call {a}', channel, spec, plugin_file)


@do
def define_autocmd(channel: int, spec: RpcHandlerSpec, plugin_name: str, plugin_file: str) -> NvimIO[DefinedHandler]:
    yield NvimIO.cmd_sync(f'augroup {plugin_name}')
    result = yield define_handler_io(lambda a: f'call {a}', channel, spec, plugin_file)
    yield NvimIO.cmd_sync(f'augroup end')
    yield NvimIO.pure(result)


def define_handler(channel: int, spec: RpcHandlerSpec, plugin_name: str, plugin_file: str) -> NvimIO[DefinedHandler]:
    if spec.tpe == 'function':
        return define_function(channel, spec, plugin_file)
    elif spec.tpe == 'command':
        return define_command(channel, spec, plugin_file)
    elif spec.tpe == 'autocmd':
        return define_autocmd(channel, spec, plugin_name, plugin_file)
    else:
        return NvimIO.failed(f'invalid type for {spec}')


def rpc_handlers(plugin_class: type) -> List[RpcHandlerSpec]:
    return Lists.wrap(inspect.getmembers(plugin_class)).flat_map2(handler)

__all__ = ('RpcHandlerSpec', 'handler', 'define_handler', 'rpc_handlers')
