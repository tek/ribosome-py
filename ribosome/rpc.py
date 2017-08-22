import inspect
from types import FunctionType
from typing import TypeVar

from amino import Map, Maybe, Lists, List, _, L
from amino.util.string import camelcaseify, ToStr

from ribosome.nvim import NvimFacade
from ribosome.logging import ribo_log

A = TypeVar('A')


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

    def _arg_desc(self) -> List[str]:
        return List(self.name, self.tpe, self.sync, self.opts, self.method, self.prefix)


def handler(method_name: str, fun: FunctionType) -> Maybe[RpcHandlerSpec]:
    def get(name: str) -> Maybe[A]:
        return Maybe(getattr(fun, name, None))
    return (
        List('_nvim_rpc_spec', '_nvim_rpc_method_name', '_nvim_prefix_plugin_path')
        .traverse(get, Maybe)
        .flat_map3(RpcHandlerSpec.cons)
    )


def register_handler_args(host: str, spec: RpcHandlerSpec, plugin_file: str) -> List[str]:
    pre = f'{plugin_file}:' if spec.prefix else ''
    rpc_method = f'{pre}{spec.method}'
    fun_prefix = camelcaseify(spec.tpe)
    return List(f'remote#define#{fun_prefix}OnHost', host, rpc_method, spec.sync, spec.name, spec.opts)


def define_handler(vim: NvimFacade, host: str, spec: RpcHandlerSpec, plugin_file: str) -> None:
    ribo_log.debug1(lambda: f'defining {spec} on {host}')
    args = register_handler_args(host, spec, plugin_file)
    return vim.call(*args)


def setup_rpc(vim: NvimFacade, host: str, plugin_class: type) -> List[str]:
    plugin_file = inspect.getfile(plugin_class)
    test_cmd_name = f'{camelcaseify(host)}Start'
    if not vim.command_exists(test_cmd_name):
        rp_handlers = Lists.wrap(inspect.getmembers(plugin_class)).flat_map2(handler)
        return rp_handlers / L(define_handler)(vim, host, _, plugin_file)
    else:
        return List()

__all__ = ('setup_rpc', 'RpcHandlerSpec')
