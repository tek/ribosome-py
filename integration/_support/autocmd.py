from amino import Map, List, Just

from ribosome.compute.api import prog
from ribosome.config.component import Component
from ribosome.rpc.api import rpc
from ribosome.config.config import Config, NoData
from ribosome.nvim.api.variable import variable_set
from ribosome.nvim.io.state import NS
from ribosome.rpc.data.prefix_style import Plain

val = 71


@prog.unit
def trans1() -> NS[NoData, None]:
    return NS.lift(variable_set('autocmd_success', val))


core: Component = Component.cons('core')


autocmd_spec_config: Config = Config.cons(
    name='plug',
    components=Map(core=core),
    rpc=List(
        rpc.autocmd(trans1).conf(name=Just('vim_resized'), prefix=Plain()),
    ),
    internal_component=False,
)

__all__ = ('autocmd_spec_config',)
