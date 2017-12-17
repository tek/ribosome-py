from typing import TypeVar, Any

from amino.state import EitherState, MaybeState, State
from amino import do, Do, __, Either, _, List, Map, Maybe, Lists, Just
from amino.json import dump_json
from amino.boolean import true
from amino.dat import Dat
from amino.lenses.lens import lens

from ribosome.trans.api import trans
from ribosome.plugin_state import PluginState
from ribosome.request.handler.handler import RequestHandler
from ribosome.request.handler.prefix import Full
from ribosome.trans.messages import ShowLogInfo, UpdateComponentState, Quit
from ribosome.components.scratch import Mapping
from ribosome.config import Config
from ribosome.dispatch.data import Dispatch, Internal, SendMessage, Trans

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


class PatchQuery(Dat['PatchQuery']):

    def __init__(self, query: str, data: Map[str, Any]) -> None:
        self.query = query
        self.data = data


class UpdateQuery(Dat['UpdateQuery']):

    def __init__(self, patch: Maybe[PatchQuery]) -> None:
        self.patch = patch


@do(MaybeState[D, None])
def patch_update(query: PatchQuery) -> Do:
    l = Lists.split(query.query, '.').fold_m(Just(lens))(Maybe.getattr)
    lns = yield MaybeState.lift(l)
    yield MaybeState.modify(lns.modify(__.typed_copy(**query.data)))


@trans.free.unit(trans.st)
@do(MaybeState[D, None])
def update_state(query: UpdateQuery) -> Do:
    yield query.patch / patch_update | MaybeState.pure(None)


message_log_handler = RequestHandler.trans_function(message_log)(prefix=Full(), internal=true, sync=true)
trans_log_handler = RequestHandler.trans_function(trans_log)(prefix=Full(), internal=true, sync=true)
set_log_level_handler = RequestHandler.trans_function(set_log_level)(prefix=Full(), internal=true)
show_log_info_handler = RequestHandler.msg_cmd(ShowLogInfo)(prefix=Full(), internal=true)
update_state_handler = RequestHandler.trans_cmd(update_state)(json=true)
update_component_state_handler = RequestHandler.msg_cmd(UpdateComponentState)(json=true)
mapping_handler = RequestHandler.msg_fun(Mapping)(prefix=Full())
quit_handler = RequestHandler.msg_cmd(Quit)(prefix=Full())
state_handler = RequestHandler.trans_function(state_data)(name='state', internal=true, sync=true)
rpc_handlers_handler = RequestHandler.trans_function(rpc_handlers)(internal=true, sync=true, prefix=Full())


def internal_dispatchers(config: Config) -> List[Dispatch]:
    return List(
        Internal(message_log_handler),
        Internal(trans_log_handler),
        Internal(set_log_level_handler),
        SendMessage(show_log_info_handler),
        Trans(update_state_handler),
        SendMessage(update_component_state_handler),
        SendMessage(mapping_handler),
        SendMessage(quit_handler),
        Internal(state_handler),
        Internal(rpc_handlers_handler),
    )


__all__ = ('internal_dispatchers',)
