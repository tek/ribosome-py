from amino.boolean import true
from amino import List, Just

from ribosome.components.internal.prog import (program_log, set_log_level, update_state, update_component_state,
                                               state_data, rpc_handlers, poll, append_python_path, show_python_path,
                                               enable_components, mapping, internal_init)
from ribosome.request.handler.prefix import Full
from ribosome.config.component import Component
from ribosome.request.handler.handler import rpc


program_log_handler = rpc.write(program_log).conf(prefix=Full(), sync=true)
set_log_level_handler = rpc.write(set_log_level).conf(prefix=Full())
update_state_handler = rpc.write(update_state).conf(json=true)
update_component_state_handler = rpc.write(update_component_state).conf(json=true)
state_handler = rpc.write(state_data).conf(name=Just('state'), sync=true, prefix=Full())
rpc_handlers_handler = rpc.write(rpc_handlers).conf(internal=true, sync=true, prefix=Full())
poll_handler = rpc.write(poll).conf(prefix=Full())
append_python_path_handler = rpc.write(append_python_path).conf(prefix=Full())
show_python_path_handler = rpc.write(show_python_path).conf(prefix=Full())
enable_components_handler = rpc.write(enable_components).conf(prefix=Full())
map_handler = rpc.write(mapping).conf(name=Just('map'), prefix=Full())
internal_init_handler = rpc.write(internal_init).conf(prefix=Full())


internal: Component = Component.cons(
    'internal',
    rpc=List(
        program_log_handler,
        set_log_level_handler,
        update_state_handler,
        update_component_state_handler,
        state_handler,
        rpc_handlers_handler,
        poll_handler,
        append_python_path_handler,
        show_python_path_handler,
        enable_components_handler,
        map_handler,
        internal_init_handler,
    ),
)


__all__ = ('internal',)
