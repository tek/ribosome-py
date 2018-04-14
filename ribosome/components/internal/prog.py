import sys
from typing import TypeVar, Any, Iterable
from uuid import UUID

from lenses import UnboundLens

from amino.state import EitherState
from amino import do, Do, __, Either, _, Map, Maybe, Lists, Just, Regex, L, IO, Try
from amino.json import dump_json
from amino.dat import Dat
from amino.lenses.lens import lens
from amino.regex import Match

from ribosome.compute.api import prog
from ribosome.data.plugin_state import PluginState
from ribosome.nvim.io.state import NS
from ribosome.config.component import ComponentData
from ribosome.config.settings import Settings
from ribosome.compute.prog import Program, Prog, bind_nullary_program
from ribosome.util.setting import setting
from ribosome.config.basic_config import NoData
from ribosome.components.internal.update import undef_handlers, def_handlers

D = TypeVar('D')
S = TypeVar('S', bound=Settings)
CC = TypeVar('CC')


@prog.result
@do(EitherState[ComponentData[PluginState[S, D, CC], NoData], str])
def program_log() -> Do:
    yield EitherState.inspect_f(lambda s: dump_json(s.main.program_log))


@prog.unit
def set_log_level(level: str) -> NS[PluginState[S, D, CC], None]:
    handler = yield NS.inspect_f(_.file_log_handler)
    handler.setLevel(level)


@prog.result
@do(EitherState[ComponentData[PluginState[S, D, CC], NoData], str])
def state_data() -> Do:
    yield EitherState.inspect_f(lambda s: dump_json(s.main.data))


@prog.result
def rpc_handlers() -> EitherState[PluginState[S, D, CC], str]:
    return EitherState.inspect_f(lambda s: dump_json(s.main.distinct_specs))


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


@do(NS[PluginState[S, D, CC], None])
def patch_update(query: PatchQuery) -> Do:
    lns = yield NS.m(mk_lens(query.query), f'invalid state update query: {query.query}')
    lns1 = lens.data & lns
    yield NS.modify(lns1.modify(__.typed_copy(**query.data)))


@prog.unit
@do(NS[PluginState[S, D, CC], None])
def update_state(query: UpdateQuery) -> Do:
    yield query.patch / patch_update | NS.pure(None)


@do(NS[PluginState[S, D, CC], None])
def patch_update_component(comp: str, query: PatchQuery) -> Do:
    lns = yield NS.m(mk_lens(query.query), f'invalid component state update query for {comp}: {query.query}')
    yield NS.modify(__.modify_component_data(comp, lns.modify(__.typed_copy(**query.data))))


@prog.unit
@do(NS[PluginState[S, D, CC], None])
def update_component_state(comp: str, query: UpdateQuery) -> Do:
    yield query.patch / L(patch_update_component)(comp, _) | NS.pure(None)


@prog.unit
def poll() -> NS[D, None]:
    return NS.unit


@prog.unit
def append_python_path(path: str) -> NS[D, None]:
    return NS.from_io(IO.delay(sys.path.append, path))


@prog.result
def show_python_path() -> NS[D, Iterable[str]]:
    return NS.pure(sys.path)


# FIXME need to update component type map
@prog.unit
@do(NS[PluginState[S, D, CC], None])
def enable_components(*names: str) -> Do:
    comps = (
        yield NS.inspect_either(
            __.comp.available.lift_all(*names).to_either(f'couldn\'t find some components: {names}'))
    )
    yield undef_handlers()
    yield NS.modify(lens.components.all.modify(__.add(comps)))
    yield def_handlers()
    print


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


@prog.result
@do(NS[PluginState[S, D, CC], Program])
def mapping_handler(uuid: UUID, keys: str) -> Do:
    yield NS.inspect_either(lambda a: a.active_mappings.lift(uuid).to_either(f'no handler for mapping `{keys}`'))


@prog.do
@do(Prog)
def mapping(uuid_s: str, keys: str) -> Do:
    uuid = yield Prog.from_either(Try(UUID, hex=uuid_s))
    handler = yield mapping_handler(uuid, keys)
    yield handler()


@prog.result
@do(NS[PluginState[S, D, CC], Maybe[Program]])
def internal_init_trans() -> Do:
    yield NS.inspect(_.init)


@prog.do
@do(Prog)
def internal_init() -> Do:
    enabled = yield prog(setting)(_.run_internal_init)
    if enabled:
        handler = yield internal_init_trans()
        yield handler / bind_nullary_program | Prog.unit


__all__ = ('internal_init', 'mapping', 'MapOptions', 'enable_components', 'show_python_path', 'append_python_path',
           'poll', 'program_log', 'set_log_level', 'state_data', 'rpc_handlers', 'update_state', 'update_component_state')
