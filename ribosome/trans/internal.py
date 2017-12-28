import sys
from typing import TypeVar, Any, Iterable

from amino.state import EitherState, MaybeState

from lenses import UnboundLens
from amino import do, Do, __, Either, _, List, Map, Maybe, Lists, Just, Regex, L, IO, Nil
from amino.json import dump_json
from amino.boolean import true
from amino.dat import Dat
from amino.lenses.lens import lens
from amino.regex import Match

from ribosome.trans.api import trans
from ribosome.plugin_state import PluginState
from ribosome.request.handler.handler import RequestHandler
from ribosome.request.handler.prefix import Full
from ribosome.trans.messages import ShowLogInfo
from ribosome.components.scratch import Mapping
from ribosome.nvim.io import NS
from ribosome.dispatch.component import Component
from ribosome.config.settings import Settings

D = TypeVar('D')
S = TypeVar('S', bound=Settings)


@trans.free.result(trans.st)
@do(EitherState[PluginState[S, D], str])
def message_log() -> Do:
    yield EitherState.inspect_f(__.message_log.traverse(dump_json, Either))


@trans.free.result(trans.st)
@do(EitherState[PluginState[S, D], str])
def trans_log() -> Do:
    yield EitherState.inspect_f(lambda s: dump_json(s.trans_log))


@trans.free.unit(trans.st)
def set_log_level(level: str) -> None:
    handler = yield MaybeState.inspect_f(_.file_log_handler)
    handler.setLevel(level)


@trans.free.result(trans.st)
def state_data() -> str:
    return EitherState.inspect_f(lambda s: dump_json(s.data))


@trans.free.result(trans.st)
def rpc_handlers() -> EitherState[D, str]:
    return EitherState.inspect_f(lambda s: dump_json(s.dispatch_config.distinct_specs))


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


@trans.free.unit(trans.st)
@do(MaybeState[D, None])
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


@trans.free.unit(trans.st)
@do(NS[PluginState[S, D], None])
def enable_components(*names: str) -> Do:
    from ribosome.dispatch.update import update_rpc
    comps = (
        yield NS.inspect_either(
            __.config.components.lift_all(*names).to_either(f'couldn\'t find some components: {names}'))
    )
    yield NS.modify(lens.components.all.modify(__.add(comps)))
    yield update_rpc()


message_log_handler = RequestHandler.trans_function(message_log)(prefix=Full(), internal=true, sync=true)
trans_log_handler = RequestHandler.trans_function(trans_log)(prefix=Full(), internal=true, sync=true)
set_log_level_handler = RequestHandler.trans_function(set_log_level)(prefix=Full(), internal=true)
show_log_info_handler = RequestHandler.msg_cmd(ShowLogInfo)(prefix=Full(), internal=true)
update_state_handler = RequestHandler.trans_cmd(update_state)(json=true)
update_component_state_handler = RequestHandler.trans_cmd(update_component_state)(internal=true, json=true)
mapping_handler = RequestHandler.msg_fun(Mapping)(prefix=Full())
state_handler = RequestHandler.trans_function(state_data)(name='state', internal=true, sync=true)
rpc_handlers_handler = RequestHandler.trans_function(rpc_handlers)(internal=true, sync=true, prefix=Full())
poll_handler = RequestHandler.trans_cmd(poll)(prefix=Full())
append_python_path_handler = RequestHandler.trans_function(append_python_path)(prefix=Full())
show_python_path_handler = RequestHandler.trans_function(show_python_path)(prefix=Full())
enable_components_handler = RequestHandler.trans_cmd(enable_components)(prefix=Full(), internal=true)


internal = Component.cons(
    'internal',
    request_handlers=List(
        message_log_handler,
        trans_log_handler,
        set_log_level_handler,
        show_log_info_handler,
        update_state_handler,
        update_component_state_handler,
        mapping_handler,
        state_handler,
        rpc_handlers_handler,
        poll_handler,
        append_python_path_handler,
        show_python_path_handler,
        enable_components_handler,
    ),
    handlers=Nil,
)


__all__ = ('internal',)
