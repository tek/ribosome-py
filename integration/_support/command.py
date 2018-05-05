from amino import Map, List, Just, do, Do

from ribosome.compute.api import prog
from ribosome.config.component import Component
from ribosome.rpc.api import rpc
from ribosome.config.config import Config, NoData
from ribosome.nvim.api.variable import variable_set, variable_raw
from ribosome.nvim.io.state import NS

val = 71


@prog.unit
@do(NS[NoData, None])
def trans1() -> Do:
    yield NS.lift(variable_set('command_success', val))


core: Component = Component.cons('core')


command_spec_config: Config = Config.cons(
    name='plug',
    components=Map(core=core),
    rpc=List(
        rpc.write(trans1).conf(name=Just('trans_cmd')),
    ),
    internal_component=False,
)

__all__ = ('command_spec_config',)
