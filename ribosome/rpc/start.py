from ribosome.rpc.comm import Comm
from ribosome.config.config import Config

from amino import IO
from ribosome.host import cons_state
from ribosome.data.plugin_state_holder import PluginStateHolder
from ribosome.rpc.handle_receive import rpc_receive
from ribosome.rpc.handle import rpc_error


def start_comm(comm: Comm, config: Config) -> IO[None]:
    state = cons_state(config)
    holder = PluginStateHolder.strict(state)
    return comm.rpc.start_processing(rpc_receive(comm, holder), rpc_error(comm))


__all__ = ('start_comm',)
