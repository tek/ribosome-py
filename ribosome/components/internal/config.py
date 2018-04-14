from amino.boolean import true
from amino import List

from ribosome.request.handler.handler import RequestHandler
from ribosome.components.internal.prog import (program_log, set_log_level, update_state, update_component_state,
                                               state_data, rpc_handlers, poll, append_python_path, show_python_path,
                                               enable_components, mapping, internal_init)
from ribosome.request.handler.prefix import Full
from ribosome.config.component import Component


program_log_handler = RequestHandler.trans_function(program_log)(prefix=Full(), sync=true)
set_log_level_handler = RequestHandler.trans_function(set_log_level)(prefix=Full())
update_state_handler = RequestHandler.trans_cmd(update_state)(json=true)
update_component_state_handler = RequestHandler.trans_cmd(update_component_state)(json=true)
state_handler = RequestHandler.trans_function(state_data)(name='state', sync=true, prefix=Full())
rpc_handlers_handler = RequestHandler.trans_function(rpc_handlers)(internal=true, sync=true, prefix=Full())
poll_handler = RequestHandler.trans_cmd(poll)(prefix=Full())
append_python_path_handler = RequestHandler.trans_function(append_python_path)(prefix=Full())
show_python_path_handler = RequestHandler.trans_function(show_python_path)(prefix=Full())
enable_components_handler = RequestHandler.trans_cmd(enable_components)(prefix=Full())
map_handler = RequestHandler.trans_function(mapping)(name='map', prefix=Full())
internal_init_handler = RequestHandler.trans_function(internal_init)(prefix=Full())


internal: Component = Component.cons(
    'internal',
    request_handlers=List(
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
