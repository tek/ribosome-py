import inspect
from types import FunctionType

from amino import Map, Maybe, Lists, List, Path
from amino.util.string import camelcaseify

from ribosome.nvim import NvimFacade
from ribosome.logging import ribo_log


class HandlerSpec:

    def __init__(self, tpe: str, sync: int, name: str, opts: dict) -> None:
        self.tpe = tpe
        self.sync = int(sync) if isinstance(sync, bool) else sync
        self.name = name
        self.opts = opts

    @staticmethod
    def cons(data: Map) -> Maybe['HandlerSpec']:
        return data.get_all('type', 'sync', 'name', 'opts').map4(HandlerSpec)


def handler(method_name: str, fun: FunctionType) -> Maybe[HandlerSpec]:
    return Maybe(getattr(fun, '_nvim_rpc_spec', None)) / Map // HandlerSpec.cons


def register_handler_args(host: str, spec: HandlerSpec, plugin_file: Path) -> List[str]:
    pat = spec.opts.get('pattern', '*')
    suf = f':{pat}' if type == 'autocmd' else ''
    rpc_method = f'{plugin_file}:{spec.tpe}:{spec.name}{suf}'
    fun_prefix = camelcaseify(spec.tpe)
    return List(f'remote#define#{fun_prefix}OnHost', host, rpc_method, spec.sync, spec.name, spec.opts)


def setup_rpc(vim: NvimFacade, name: str, plugin_class: type) -> None:
    plugin_file = inspect.getfile(plugin_class)
    ribo_log.test('-------------')
    ribo_log.test(plugin_file)
    if not vim.command_exists(f'{camelcaseify(name)}Start'):
        rp_handlers = Lists.wrap(inspect.getmembers(plugin_class)).flat_map2(handler)
        for spec in rp_handlers:
            ribo_log.test(spec)
            args = register_handler_args(name, spec, plugin_file)
            ribo_log.test(args)
            r = vim.call(*args)
            ribo_log.test(r)

__all__ = ('setup_rpc',)
