from amino import Map, List

from ribosome.compute.api import prog
from ribosome.config.component import Component
from ribosome.request.handler.handler import rpc
from ribosome.config.config import Config, NoData
from ribosome.nvim.api.variable import variable_set
from ribosome.nvim.io.state import NS
from ribosome import ribo_log

val = 71


@prog.unit
def trans1() -> NS[NoData, None]:
    return NS.lift(variable_set('command_success', val))


core: Component = Component.cons('core')


command_spec_config: Config = Config.cons(
    name='plug',
    components=Map(core=core),
    rpc=List(
        rpc.write(trans1).conf(name='trans_cmd'),
    ),
    internal_component=False,
)

__all__ = ('command_spec_config',)
