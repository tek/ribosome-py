import inspect
from types import FunctionType
from typing import TypeVar, Callable, Union

from amino import Map, Maybe, Lists, List, _, L, Either
from amino.util.string import camelcaseify, ToStr

from ribosome.nvim import NvimFacade, NvimIO
from ribosome.logging import ribo_log

A = TypeVar('A')


def mk_rpc_opt(key: str, value: Union[str, int]) -> str:
    return (
        f'-nargs={value}'
        if key == 'nargs' else
        ''
    )


def mk_rpc_arg(key: str, value: Union[str, int]) -> str:
    return (
        f'[<f-args>]'
        if key == 'nargs' else
        ''
    )


class RpcHandlerSpec(ToStr):

    def __init__(self, tpe: str, sync: int, name: str, opts: dict, method: str, prefix: bool) -> None:
        self.tpe = tpe
        self.sync = int(sync) if isinstance(sync, bool) else sync
        self.name = name
        self.opts = opts
        self.method = method
        self.prefix = prefix

    @staticmethod
    def cons(spec: dict, method: str, prefix: bool) -> Maybe['RpcHandlerSpec']:
        return Map(spec).get_all('type', 'sync', 'name', 'opts').map4(L(RpcHandlerSpec)(_, _, _, _, method, prefix))

    @staticmethod
    def cmd(sync: int, name: str, opts: dict) -> 'RpcHandlerSpec':
        method = f'command:{name}'
        return RpcHandlerSpec('command', sync, name, opts, method, True)

    @staticmethod
    def fun(sync: int, name: str, opts: dict) -> 'RpcHandlerSpec':
        method = f'function:{name}'
        return RpcHandlerSpec('function', sync, name, opts, method, True)

    @staticmethod
    def decode(data: dict) -> 'Maybe[RpcHandlerSpec]':
        return Map(data).get_all('method', 'prefix').flat_map2(L(RpcHandlerSpec.cons)(data, _, _))

    def _arg_desc(self) -> List[str]:
        return List(self.name, self.tpe, self.sync, self.opts, self.method, self.prefix)

    @property
    def rpc_function(self) -> str:
        return 'rpcrequest' if self.sync else 'rpcnotify'

    @property
    def rpc_opts(self) -> List[str]:
        return Map(self.opts).map2(mk_rpc_opt)

    @property
    def rpc_args(self) -> List[str]:
        return Map(self.opts).map2(mk_rpc_arg)

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


def handler(method_name: str, fun: FunctionType) -> Maybe[RpcHandlerSpec]:
    def get(name: str) -> Maybe[A]:
        return Maybe.getattr(fun, name)
    return (
        List('_nvim_rpc_spec', '_nvim_rpc_method_name', '_nvim_prefix_plugin_path')
        .traverse(get, Maybe)
        .flat_map3(RpcHandlerSpec.cons)
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


def _define_handler(rhs: Callable[[str], str], channel: int, spec: RpcHandlerSpec, plugin_file: str
                    ) -> NvimIO[DefinedHandler]:
    ribo_log.debug1(lambda: f'defining {spec} on channel {channel}')
    fun = spec.rpc_function
    method = spec.rpc_method(plugin_file)
    args = spec.rpc_args.cons(f"'{method}'").join_comma
    rpc_call = f'{fun}({channel}, {args})'
    rhs = rhs(rpc_call)
    cmd = f'{spec.tpe}! {spec.rpc_opts.join_tokens} {spec.name} {rhs}'
    return NvimIO.cmd_sync(cmd).replace(DefinedHandler(spec, channel))


def define_function(channel: int, spec: RpcHandlerSpec, plugin_file: str) -> NvimIO[DefinedHandler]:
    return _define_handler(lambda call: f'(...)\nreturn {call}\nendfunction', channel, spec, plugin_file)


def define_command(channel: int, spec: RpcHandlerSpec, plugin_file: str) -> NvimIO[DefinedHandler]:
    return _define_handler(lambda a: f'call {a}', channel, spec, plugin_file)


def define_autocmd(channel: int, spec: RpcHandlerSpec, plugin_file: str) -> NvimIO[DefinedHandler]:
    return _define_handler(lambda a: f'call {a}', channel, spec, plugin_file)


def define_handler(channel: int, spec: RpcHandlerSpec, plugin_file: str) -> NvimIO[DefinedHandler]:
    if spec.tpe == 'function':
        return define_function(channel, spec, plugin_file)
    elif spec.tpe in ('command', 'autocmd'):
        return define_command(channel, spec, plugin_file)
    else:
        return NvimIO.failed(f'invalid type for {spec}')


def rpc_handlers(plugin_class: type) -> List[RpcHandlerSpec]:
    return Lists.wrap(inspect.getmembers(plugin_class)).flat_map2(handler)


def setup_rpc(vim: NvimFacade, host: str, plugin_class: type) -> List[str]:
    plugin_file = inspect.getfile(plugin_class)
    test_cmd_name = f'{camelcaseify(host)}Start'
    if not vim.command_exists(test_cmd_name):
        handlers = rpc_handlers(plugin_class)
        return handlers / L(define_handler)(vim, host, _, plugin_file)
    else:
        return List()

__all__ = ('RpcHandlerSpec', 'handler', 'define_handler', 'rpc_handlers', 'setup_rpc')
