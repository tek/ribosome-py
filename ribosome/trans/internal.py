import sys
from typing import TypeVar, Any, Iterable
from uuid import UUID

from amino.state import EitherState, MaybeState, State

from lenses import UnboundLens
from amino import do, Do, __, Either, _, List, Map, Maybe, Lists, Just, Regex, L, IO, Nil, Try
from amino.json import dump_json
from amino.boolean import true, false
from amino.dat import Dat
from amino.lenses.lens import lens
from amino.regex import Match

from ribosome.trans.api import trans
from ribosome.plugin_state import PluginState
from ribosome.request.handler.handler import RequestHandler
from ribosome.request.handler.prefix import Full
from ribosome.trans.messages import ShowLogInfo
from ribosome.nvim.io import NS
from ribosome.dispatch.component import Component, ComponentData
from ribosome.config.settings import Settings
from ribosome.dispatch.update import update_rpc
from ribosome.nvim import NvimIO
from ribosome.trans.handler import FreeTrans
from ribosome.trans.action import TransM
from ribosome.config.config import NoData
from ribosome import ribo_log

D = TypeVar('D')
S = TypeVar('S', bound=Settings)
CC = TypeVar('CC')


@trans.free.result(trans.st)
@do(EitherState[PluginState[S, D, CC], str])
def message_log() -> Do:
    yield EitherState.inspect_f(__.message_log.traverse(dump_json, Either))


@trans.free.result(trans.st, internal=true)
@do(EitherState[ComponentData[PluginState[S, D, CC], NoData], str])
def trans_log() -> Do:
    yield EitherState.inspect_f(lambda s: dump_json(s.main.trans_log))


@trans.free.unit(trans.st)
def set_log_level(level: str) -> None:
    handler = yield MaybeState.inspect_f(_.file_log_handler)
    handler.setLevel(level)


@trans.free.result(trans.st, internal=true)
@do(EitherState[ComponentData[PluginState[S, D, CC], NoData], str])
def state_data() -> Do:
    yield EitherState.inspect_f(lambda s: dump_json(s.main.data))


@trans.free.result(trans.st, internal=true)
def rpc_handlers() -> EitherState[PluginState[S, D, CC], str]:
    return EitherState.inspect_f(lambda s: dump_json(s.main.dispatch_config.distinct_specs))


class PatchQuery(Dat['PatchQuery']):

    def __init__(self, query: str, data: Map[str, Any]) -> None:
        self.query = query
        self.data = data


class UpdateQuery(Dat['UpdateQuery']):

    def __init__(self, patch: Maybe[PatchQuery]) -> None:
        self.patch = patch


find_rex = Regex(r'(?P<id>\w+)\((?P<key>\w+)=(?P<value>\w+)\)')


@do(Maybe[UnboundLens])
def find_lens(z: UnboundLens, m: Match) -> Do:
    id, key, value = yield m.all_groups('id', 'key', 'value').to_maybe
    yield Just(z.getattr_(id).each_().filter_(lambda a: Maybe.getattr(a, key).contains(value)))


# TODO `Regex.match_as(tpe)` that constructs a `Dat` from the `Match`
def lens_step(z: UnboundLens, s: str) -> Maybe[UnboundLens]:
    return find_rex.match(s) / L(find_lens)(z, _) | (lambda: Maybe.getattr(z, s))


def mk_lens(query: str) -> UnboundLens:
    return Lists.split(query, '.').fold_m(Just(lens))(lens_step)


@do(MaybeState[D, None])
def patch_update(query: PatchQuery) -> Do:
    lns = yield MaybeState.lift(mk_lens(query.query))
    lns1 = lens.main & lns
    yield MaybeState.modify(lns1.modify(__.typed_copy(**query.data)))


@trans.free.unit(trans.st)
@do(MaybeState[D, None])
def update_state(query: UpdateQuery) -> Do:
    yield query.patch / patch_update | MaybeState.pure(None)


@do(MaybeState[D, None])
def patch_update_component(comp: str, query: PatchQuery) -> Do:
    lns = yield MaybeState.lift(mk_lens(query.query))
    lns1 = lens.component_data.GetItem(comp) & lns
    yield MaybeState.modify(lns1.modify(__.typed_copy(**query.data)))


@trans.free.unit(trans.st, internal=true, component=false)
@do(MaybeState[PluginState[S, D, CC], None])
def update_component_state(comp: str, query: UpdateQuery) -> Do:
    yield query.patch / L(patch_update_component)(comp, _) | MaybeState.pure(None)


@trans.free.unit()
def poll() -> None:
    pass


@trans.free.unit(trans.io)
def append_python_path(path: str) -> IO[None]:
    return IO.delay(sys.path.append, path)


@trans.free.result()
def show_python_path() -> Iterable[str]:
    return sys.path


@trans.free.unit(trans.st, component=false)
@do(NS[PluginState[S, D, CC], None])
def enable_components(*names: str) -> Do:
    comps = (
        yield NS.inspect_either(
            __.config.components.lift_all(*names).to_either(f'couldn\'t find some components: {names}'))
    )
    yield NS.modify(lens.components.all.modify(__.add(comps)))
    yield update_rpc()


class MapOptions(Dat['MapOptions']):

    @staticmethod
    def cons(
            buffer: int=None,
    ) -> 'MapOptions':
        return MapOptions(
            Maybe.optional(buffer),
        )

    def __init__(self, buffer: Maybe[int]) -> None:
        self.buffer = buffer


@do(EitherState[PluginState[S, D, CC], FreeTrans])
def mapping_handler(uuid: UUID, keys: str) -> Do:
    yield EitherState.inspect_f(lambda a: a.active_mappings.lift(uuid).to_either(f'no handler for mapping `{keys}`'))


@trans.free.do()
@do(TransM)
def mapping(uuid_s: str, keys: str) -> Do:
    uuid = yield TransM.from_either(Try(UUID, hex=uuid_s))
    handler = yield mapping_handler(uuid, keys).trans_with(component=false, internal=true)
    yield handler.m


message_log_handler = RequestHandler.trans_function(message_log)(prefix=Full(), sync=true)
trans_log_handler = RequestHandler.trans_function(trans_log)(prefix=Full(), sync=true)
set_log_level_handler = RequestHandler.trans_function(set_log_level)(prefix=Full())
show_log_info_handler = RequestHandler.msg_cmd(ShowLogInfo)(prefix=Full())
update_state_handler = RequestHandler.trans_cmd(update_state)(json=true)
update_component_state_handler = RequestHandler.trans_cmd(update_component_state)(json=true)
state_handler = RequestHandler.trans_function(state_data)(name='state', sync=true, prefix=Full())
rpc_handlers_handler = RequestHandler.trans_function(rpc_handlers)(internal=true, sync=true, prefix=Full())
poll_handler = RequestHandler.trans_cmd(poll)(prefix=Full())
append_python_path_handler = RequestHandler.trans_function(append_python_path)(prefix=Full())
show_python_path_handler = RequestHandler.trans_function(show_python_path)(prefix=Full())
enable_components_handler = RequestHandler.trans_cmd(enable_components)(prefix=Full())
map_handler = RequestHandler.trans_function(mapping)(name='map', prefix=Full(), json=true)


internal = Component.cons(
    'internal',
    request_handlers=List(
        message_log_handler,
        trans_log_handler,
        set_log_level_handler,
        show_log_info_handler,
        update_state_handler,
        update_component_state_handler,
        state_handler,
        rpc_handlers_handler,
        poll_handler,
        append_python_path_handler,
        show_python_path_handler,
        enable_components_handler,
        map_handler,
    ),
    handlers=Nil,
)


__all__ = ('internal',)
