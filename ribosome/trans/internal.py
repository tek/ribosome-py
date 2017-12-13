from typing import TypeVar

from amino.state import EitherState, MaybeState
from amino import do, Do, __, Either, _, List
from amino.json import dump_json

from ribosome.trans.api import trans
from ribosome.plugin_state import PluginState
from ribosome.request.handler.handler import RequestHandler
from ribosome.request.handler.prefix import Full
from ribosome.trans.messages import ShowLogInfo, UpdateState, Stage1, Quit
from ribosome.components.scratch import Mapping
from ribosome.config import Config
from ribosome.dispatch.data import Dispatch, Internal, SendMessage

D = TypeVar('D')


@trans.free.result(trans.st)
@do(EitherState[PluginState[D], str])
def message_log() -> Do:
    yield EitherState.inspect_f(__.message_log.traverse(dump_json, Either))


@trans.free.result(trans.st)
@do(EitherState[PluginState[D], str])
def trans_log() -> Do:
    yield EitherState.inspect_f(lambda s: dump_json(s.trans_log))


@trans.free.unit(trans.st)
def set_log_level(level: str) -> None:
    handler = yield MaybeState.inspect_f(_.file_log_handler)
    handler.setLevel(level)


@trans.free.result(trans.st)
def state_data() -> str:
    return EitherState.inspect_f(lambda s: dump_json(s.data))


@trans.free.result()
def rpc_handlers() -> None:
    pass


message_log_handler = RequestHandler.trans_function(message_log)(name='message_log', prefix=Full(), internal=True,
                                                                 sync=True)
trans_log_handler = RequestHandler.trans_function(trans_log)(prefix=Full(), internal=True, sync=True)
set_log_level_handler = RequestHandler.trans_function(set_log_level)(prefix=Full(), internal=True)
show_log_info_handler = RequestHandler.msg_cmd(ShowLogInfo)(name='show_log_info', prefix=Full(), internal=True)
update_state_handler = RequestHandler.json_msg_cmd(UpdateState)(name='update_state', prefix=Full())
mapping_handler = RequestHandler.msg_fun(Mapping)(name='mapping', prefix=Full())
quit_handler = RequestHandler.msg_cmd(Quit)(prefix=Full())
state_handler = RequestHandler.trans_function(state_data)(name='state', internal=True, sync=True)
rpc_handlers_handler = RequestHandler.trans_function(rpc_handlers)(name='rpc_handlers', internal=True, sync=True,
                                                                   prefix=Full())


def internal_dispatchers(config: Config) -> List[Dispatch]:
    return List(
        Internal(message_log_handler),
        Internal(trans_log_handler),
        Internal(set_log_level_handler),
        SendMessage(show_log_info_handler),
        SendMessage(update_state_handler),
        SendMessage(mapping_handler),
        SendMessage(quit_handler),
        Internal(state_handler),
        Internal(rpc_handlers_handler),
    )


__all__ = ('internal_dispatchers',)
