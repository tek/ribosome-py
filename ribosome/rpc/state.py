from typing import TypeVar, Any

from amino import Nil
from amino.do import do, Do

from ribosome.config.config import Config
from ribosome.logging import nvim_logging
from ribosome.data.plugin_state import PluginState
from ribosome.nvim.io.compute import NvimIO
from ribosome.nvim.io.api import N
from ribosome.config.component import ComponentConfig
from ribosome.components.internal.update import init_rpc_plugin
from ribosome.compute.interpret import ProgIOInterpreter
from ribosome.compute.program import Program

D = TypeVar('D')
CC = TypeVar('CC')


def cons_state(
        config: Config,
        io_interpreter: ProgIOInterpreter=None,
        logger: Program[None]=None,
        **kw: Any,
) -> PluginState[D, CC]:
    data = config.basic.state_ctor()
    return PluginState.cons(
        config.basic,
        ComponentConfig(config.components),
        config.rpc,
        data,
        Nil,
        config.init,
        logger=logger,
        io_interpreter=io_interpreter,
        **kw,
    )


@do(NvimIO[PluginState[D, CC]])
def init_state_plugin(config: Config, io_interpreter: ProgIOInterpreter=None, logger: Program[None]=None) -> Do:
    log_handler = yield N.delay(nvim_logging)
    state = cons_state(config, io_interpreter, logger, log_handler=log_handler)
    yield init_rpc_plugin().run_s(state)


__all__ = ('cons_state', 'init_state',)
