from amino import List, do, Do
from amino.logging import module_log

from ribosome.compute.api import prog
from ribosome.rpc.api import rpc
from ribosome.config.config import Config, NoData
from ribosome.nvim.io.state import NS
from ribosome.config.component import NoComponentData
from ribosome.compute.ribosome import Ribosome
from ribosome.compute.ribosome_api import Ribo
from ribosome.config.setting import int_setting

log = module_log()
counter = int_setting('counter', 'counter', '', False)
inc = int_setting('inc', 'inc', '', False)


@prog.unit
@do(NS[Ribosome[NoData, NoComponentData, NoData], None])
def check() -> Do:
    ctr = yield Ribo.setting(counter)
    i = yield Ribo.setting(inc)
    yield NS.lift(counter.update(ctr + i))


settings_spec_config: Config = Config.cons(
    name='plug',
    rpc=List(
        rpc.write(check),
    ),
    internal_component=False,
)

__all__ = ('settings_spec_config',)
