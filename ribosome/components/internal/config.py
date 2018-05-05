from amino.boolean import true
from amino import List, Just

from ribosome.components.internal.prog import (program_log, set_log_level, update_state, update_component_state,
                                               state_data, rpc_handlers, poll, append_python_path, show_python_path,
                                               enable_components, mapping, internal_init)
from ribosome.config.component import Component
from ribosome.rpc.data.prefix_style import Full
from ribosome.rpc.api import rpc

internal: Component = Component.cons(
    'internal',
    rpc=List(
        rpc.write(program_log).conf(prefix=Full(), sync=true),
        rpc.write(set_log_level).conf(prefix=Full()),
        rpc.write(update_state).conf(json=true),
        rpc.write(update_component_state).conf(json=true),
        rpc.write(state_data).conf(name=Just('state'), sync=true, prefix=Full()),
        rpc.write(rpc_handlers).conf(internal=true, sync=true, prefix=Full()),
        rpc.write(poll).conf(prefix=Full()),
        rpc.write(append_python_path).conf(prefix=Full()),
        rpc.write(show_python_path).conf(prefix=Full()),
        rpc.write(enable_components).conf(prefix=Full()),
        rpc.write(mapping).conf(name=Just('map'), prefix=Full()),
        rpc.write(internal_init).conf(prefix=Full()),
    ),
)

__all__ = ('internal',)
